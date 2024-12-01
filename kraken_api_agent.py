#!/usr/bin/env python3

import argparse
import os
import json
import re
from datetime import datetime, timezone
import requests
import csv
from io import StringIO
from tzlocal import get_localzone

from http import server as HTTPServer
from html import escape
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs, unquote
from sys import exit

from krakensdr_control import KrakenSDRControl

# --------------- web server support ------------------------------------
direct_serve_types = {
    "html": {"content-type": "text/html", "read_type":"r"}, 
    "htm": {"content-type": "text/html", "read_type":"r"}, 
    "js": {"content-type": "text/javascript", "read_type":"r"}, 
    "map": {"content-type": "text/javascript", "read_type":"r"}, 
    "css": {"content-type": "text/css", "read_type":"r"}, 
    "csv": {"content-type": "application/octet-stream", "read_type":"r"}, 
    "jpeg": {"content-type": "image/jpeg", "read_type":"rb"}, 
    "jpg": {"content-type": "image/jpg", "read_type":"rb"}, 
    "png": {"content-type": "image/png", "read_type":"rb"}, 
    "png-binary": {"content-type": "application/octet-stream", "read_type":"rb"}, 
    "svg": {"content-type": "image/svg+xml", "read_type":"rb"}, 
    "woff": {"content-type": "application/octet-stream", "read_type":"rb"}, 
    "woff2": {"content-type": "application/octet-stream", "read_type":"rb"}, 
    "ttf": {"content-type": "application/octet-stream", "read_type":"rb"}, 
    "ico": {"content-type": "image/x-icon", "read_type":"rb"}, 
    "pdf": {"content-type": "application/pdf", "read_type":"rb"}, 
    "png-meta": {"content-type": "application/json", "read_type":"r"}, 
    "sigmf-data": {"content-type": "application/octet-stream", "read_type":"rb"}, 
    "sigmf-meta": {"content-type": "application/json", "read_type":"r"}, 
    "ann-meta": {"content-type": "text/plain", "read_type":"r"}
}

# --------------- Global Variables ------------------------------------
    
debugHTTP = False

# Set html_dir to a path and/or with an argparse to enable direct-serving web pages.
html_dir = None

krakensdr = None

# --------------- Global Functions  ------------------------------------
def convert_utc_to_local(utc_time: datetime) -> datetime:
    """
    Converts a UTC datetime object to a local timezone datetime object.
    
    Args:
        utc_time (datetime): A datetime object in UTC.
        
    Returns:
        datetime: A datetime object in the local timezone.
    """
    if utc_time.tzinfo is None:
        raise ValueError("The input datetime object must be timezone-aware (in UTC).")
    
    # Get the local timezone
    local_tz = get_localzone()
    
    # Convert the UTC time to the local timezone
    local_time = utc_time.astimezone(local_tz)
    
    return local_time
    
def fetch_and_process_csv(server_name):
    global utc_timezone
    
    """
    Fetches a CSV document from the server and processes it into a list of dictionaries.

    :param server_name: Name of the server to connect to
    :return: List of dictionaries representing CSV rows
    """
    # Construct the URL
    url = f"http://{server_name}:8081/DOA_value.html"

    # Define field mappings by position
    base_fields = [
        "Epoch Time",
        "Max DOA Angle (Degrees)",
        "Confidence Value",
        "RSSI Power (dB)",
        "Channel Frequency (Hz)",
        "Antenna Arrangement",
        "Latency (ms)",
        "Station ID",
        "Latitude",
        "Longitude",
        "GPS Heading",
        "Compass Heading",
        "Main Heading Sensor Used",
    ]
    reserved_fields = [f"Reserved Field {i}" for i in range(14, 18)]
    doa_fields = [f"DOA Power {i}" for i in range(0, 360)]
    fields = base_fields + reserved_fields + doa_fields

    try:
        # Make the HTTP GET request
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the CSV content (without headers)
        csv_content = StringIO(response.text)
        csv_reader = csv.reader(csv_content)

        # Process rows into a list of dictionaries
        rows = []
        for line_number, row in enumerate(csv_reader, start=1):
            if len(row) < len(fields):
                print(f"Skipping row {line_number} due to insufficient fields.")
                continue

            # Map fields by position
            base_data = {
                fields[i]: row[i] for i in range(len(base_fields))
            }

            # Convert specific fields to appropriate types
            try:
                base_data["Epoch Time"] = int(base_data["Epoch Time"])
                utc_time = datetime.fromtimestamp(float(base_data["Epoch Time"]) / 1000,tz=timezone.utc)
                local_time = convert_utc_to_local(utc_time)
                
                base_data["utc_timestamp"] = utc_time.strftime('%Y-%m-%d %H:%M:%S') + "Z"
                base_data["local_timestamp"] = local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                base_data["Max DOA Angle (Degrees)"] = float(base_data["Max DOA Angle (Degrees)"])
                base_data["Confidence Value"] = float(base_data["Confidence Value"])
                base_data["RSSI Power (dB)"] = float(base_data["RSSI Power (dB)"])
                base_data["Channel Frequency (Hz)"] = float(base_data["Channel Frequency (Hz)"])
                base_data["Latency (ms)"] = float(base_data["Latency (ms)"])
                base_data["Latitude"] = float(base_data["Latitude"])
                base_data["Longitude"] = float(base_data["Longitude"])
                base_data["GPS Heading"] = float(base_data["GPS Heading"])
                base_data["Compass Heading"] = float(base_data.get("Compass Heading", "NaN"))
            except ValueError as e:
                print(f"Error converting field values on row {line_number}: {e}")
                continue

            # Add DOA output as a dictionary
            doa_output = {str(degree): float(row[len(base_fields) + len(reserved_fields) + degree]) for degree in range(360)}
            base_data["DOA Output"] = doa_output

            rows.append(base_data)

        return rows

    except requests.exceptions.RequestException as e:
        print(f"Error making GET request: {e}")
        return []
    except csv.Error as e:
        print(f"Error processing CSV content: {e}")
        return []

def get_time_string():
    return "[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] "

def param_data_to_dict(req_query):
    param_data=parse_qs(req_query)

    for cur_key in param_data.keys():
        if len(param_data[cur_key]) == 1:
            param_data[cur_key] = param_data[cur_key][0]
            if param_data[cur_key].upper() == "TRUE":
                param_data[cur_key] = True
            elif param_data[cur_key].upper() == "FALSE":
                param_data[cur_key] = False
    
    return param_data
    
def build_base_dict():
    responsedict = {}
    responsedict['errcode'] = 0
    responsedict['errmsg'] = ""
    
    return responsedict
    
def return_json_dict(s,  responsedict, response_code=200):
    try:
        jsonstr = json.dumps(responsedict)

        s.send_response(response_code)
        s.send_header("Content-type", "application/json; charset=utf-8")
        s.send_header("Content-length", str(len(jsonstr)))
        s.end_headers()
        s.wfile.write(jsonstr.encode("UTF-8"))
    except Exception as e:
        print("ERROR converting dictionary to json string: " + str(e))

def return_error_json(s,  err_code,  err_msg):
    responsedict = {}
    responsedict['errcode'] = err_code
    responsedict['errmsg'] = escape(err_msg)

    return_json_dict(s, responsedict, 200)

def return_error_html(s,  err_code,  err_msg):
    try:
        s.send_response(404)
        s.send_header("Content-type", "text/html; charset=utf-8")
        s.end_headers()
        s.wfile.write(("<html><body><p>" + escape(err_msg) + "</p>").encode("utf-8"))
        s.wfile.write("</body></html>".encode("UTF-8"))
    except:
        pass

def buildAllowedIPs(allowedIPstr):
    global allowedIPs

    allowedIPs = []

    if len(allowedIPstr) > 0:
        ippattern = re.compile(r'([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})')
        if ',' in allowedIPstr:
            tmpList = allowedIPstr.split(',')
            for curItem in tmpList:
                ipStr = curItem.replace(' ', '')
                try:
                    ipValue = ippattern.search(ipStr).group(1)
                except:
                    ipValue = ""
                    print('ERROR: Unknown IP pattern: ' + ipStr)
                    exit(3)

                if len(ipValue) > 0:
                    allowedIPs.append(ipValue)
        else:
            ipStr = allowedIPstr.replace(' ', '')
            try:
                ipValue = ippattern.search(ipStr).group(1)
            except:
                ipValue = ""
                print('ERROR: Unknown IP pattern: ' + ipStr)
                return False

            if len(ipValue) > 0:
                allowedIPs.append(ipValue)

    return True

# --------------- Multithreaded HTTP Server ------------------------------------
class MultithreadHTTPServer(ThreadingMixIn, HTTPServer.HTTPServer):
    pass

# ---------------  HTTP Request Handler --------------------
# Sample handler: https://wiki.python.org/moin/BaseHttpServer
class AgentRequestHandler(HTTPServer.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        global debugHTTP

        if not debugHTTP:
            return
        else:
            HTTPServer.BaseHTTPRequestHandler(format, *args)

    def do_HEAD(s):
        global allowCors

        s.send_response(200)
        s.send_header("Content-type", "text/html")
        if allowCors:
            s.send_header("Access-Control-Allow-Origin", "*")
        s.end_headers()

    def do_POST(s):
        global allowedIPs
        
        if len(s.client_address) == 0:
            # This should have the connecting client IP.  If this isn't at least 1, something is wrong
            return

        # If the pipe gets broken mid-stream it'll throw an exception
        if len(allowedIPs) > 0:
            if s.client_address[0] not in allowedIPs:
                try:
                    print("WARN: request from unauthorized IP: " + str(s.client_address[0]))
                    
                    s.send_response(403)
                    s.send_header("Content-type", "text/html")
                    s.end_headers()
                    s.wfile.write("<html><body><p>Connections not authorized from your IP address</p>".encode("utf-8"))
                    s.wfile.write("</body></html>".encode("UTF-8"))
                except:
                    pass

                return

        # Get the size of the posted data
        try:
            length = int(s.headers['Content-Length'])
        except:
            length = 0

        if length <= 0:
            return_error_json(s,  1,  'Agent received a zero-length request.')
            return

        # Handle post requests here.
        print(get_time_string() + "Unhandled POST processing " + s.path)
        return_error_json(s,  5,  "Unhandled POST" )
            
    def do_GET(s):
        global krakensdr
        
        if len(s.client_address) == 0:
            # This should have the connecting client IP.  If this isn't at least 1, something is wrong
            return

        # If the pipe gets broken mid-stream it'll throw an exception
        if len(allowedIPs) > 0:
            if s.client_address[0] not in allowedIPs:
                try:
                    print("WARN: request from unauthorized IP: " + str(s.client_address[0]))
                    
                    s.send_response(403)
                    s.send_header("Content-type", "text/html")
                    s.end_headers()
                    s.wfile.write("<html><body><p>Connections not authorized from your IP address</p>".encode("utf-8"))
                    s.wfile.write("</body></html>".encode("UTF-8"))
                except:
                    pass

                return

        # Direct serve some file types: html, css, js, images, etc.
        try:
            req = urlparse(s.path)
        except Exception as e:
            print("ERROR parsing requested URL: " + str(e))
            return_error_html(s, 1, str(e))
            return
            
        url_path = req.path
        while url_path.startswith("/") or url_path.startswith("."):
            url_path = url_path[1:]
            
        if len(url_path) == 0:
            s.send_response(302)
            s.send_header('Location', '/index.html')
            s.end_headers()
            return

        requested_file = os.path.basename(req.path)
        file_name, ext = os.path.splitext(requested_file)
        ext = ext.replace(".", "")
        
        # Set html_dir to a directory to enable direct-serving UI files
        if html_dir is not None:
            if len(ext) > 0 and ext in direct_serve_types.keys():
                try:
                    filename = html_dir + "/" + url_path
                        
                    filename=unquote(filename)
                    
                    with open(filename, direct_serve_types[ext]['read_type']) as f:
                        contents = f.read()
                        s.send_response(200)
                        s.send_header("Content-type", direct_serve_types[ext]['content-type'] + "; charset=utf-8")
                        s.end_headers()
                        
                        if type(contents) == bytes:
                            returned_contents = contents
                        else:
                            returned_contents = contents.encode("UTF-8")
                        #if direct_serve_types[ext]['read_type'] == 'rb':
                        #else:
                        #    returned_contents = contents

                        s.wfile.write(returned_contents)
                except Exception as e:
                    print("ERROR serving non-API content: " + str(e))
                    return_error_html(s, 1, "Page not found.")
                    
                return
        
        # Start processing valid URI's
        try:
            if s.path == '/api/krakensdr/get_config':
                try:
                    responsedict = build_base_dict()
                    responsedict['settings'] = krakensdr.get_config()
                except Exception as e:
                    return_error_json(s,1,"ERROR getting config: " + str(e))
                    return
                    
                return_json_dict(s,  responsedict)
            elif s.path.startswith('/api/krakensdr/set_frequency'):
                param_data = param_data_to_dict(req.query)
                
                if not 'freq' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting freq=<value>")
                    return
                    
                try:
                    new_freq = float(param_data['freq'])
                    
                    if new_freq < 24.0 or new_freq > 1766.0:
                        return_error_json(s, 1, "Frequency range error.  Value should be in MHz and range from 24.0 - 1766.0")
                        return
                        
                    if 'gain' in param_data.keys():
                        gain = float(param_data['gain'])
                    else:
                        gain = None
                        
                    if gain is None:
                        krakensdr.set_frequency(new_freq)
                    else:
                        krakensdr.set_frequency(new_freq,save_file=False)
                        krakensdr.set_gain(gain)
                        
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path=="/api/krakensdr/get_doa":
                try:
                    doa_info = fetch_and_process_csv('localhost')
                except Exception as e:
                    return_error_json(s,1,"ERROR getting config: " + str(e))
                    return
                    
                responsedict = build_base_dict()
                if doa_info is not None:
                    responsedict['doa_info'] = doa_info[0]
                else:
                    responsedict['doa_info'] = None
                    
                return_json_dict(s,  responsedict)
            elif s.path.startswith('/api/krakensdr/set_frequency_and_vfo'):
                param_data = param_data_to_dict(req.query)
                
                if not 'freq' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting freq=<value>")
                    return
                    
                if not 'vfo_index' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_index=<index>")
                    return

                if not 'vfo_freq' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_freq=<value in Hz>")
                    return
                    
                try:
                    new_freq = float(param_data['freq'])
                    
                    if new_freq < 24.0 or new_freq > 1766.0:
                        return_error_json(s, 1, "Frequency range error.  Value should be in MHz and range from 24.0 - 1766.0")
                        return
                        
                    index = int(param_data['vfo_index'])
                    vfo_freq = float(param_data['vfo_freq'])
                    
                    if vfo_freq < 24e6 or vfo_freq > 1766e6:
                        return_error_json(s, 1, "VFO Frequency range error.  Value should be in Hz and range from 24000000 - 1766000000")
                        return
                        
                    krakensdr.set_frequency(new_freq,save_file=False)
                    krakensdr.set_vfo_frequency(index, vfo_freq)

                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path.startswith('/api/krakensdr/set_gain'):
                param_data = param_data_to_dict(req.query)
                
                if not 'gain' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting gain=<value>")
                    return
                    
                try:
                    gain = float(param_data['gain'])
                    
                    # set_gain() will throw an exception if the gain value is not valid
                    krakensdr.set_gain(gain)
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path.startswith('/api/krakensdr/set_output_vfo'):
                param_data = param_data_to_dict(req.query)
                
                if not 'vfo_index' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_index=<index>")
                    return

                try:
                    index = int(param_data['vfo_index'])
                        
                    krakensdr.set_output_vfo(index)
                    
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path.startswith('/api/krakensdr/en_optimize_short_bursts'):
                param_data = param_data_to_dict(req.query)
                
                if not 'state' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting state=[true|false]")
                    return

                try:
                    krakensdr.optimize_short_bursts(param_data['state'])
                    
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path.startswith('/api/krakensdr/set_vfo_frequency'):
                param_data = param_data_to_dict(req.query)
                
                if not 'vfo_index' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_index=<index>")
                    return

                if not 'vfo_freq' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_freq=<value in Hz>")
                    return
                    
                try:
                    index = int(param_data['vfo_index'])
                    
                    freq = float(param_data['vfo_freq'])
                    
                    if freq < 24e6 or freq > 1766e6:
                        return_error_json(s, 1, "Frequency range error.  Value should be in Hz and range from 24000000 - 1766000000")
                        return
                        
                    krakensdr.set_vfo_frequency(index, freq)
                    
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path.startswith('/api/krakensdr/set_vfo_bandwidth'):
                param_data = param_data_to_dict(req.query)
                
                if not 'vfo_index' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_index=<index>")
                    return

                if not 'vfo_bw' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  Expecting vfo_bw=<value in Hz>")
                    return
                    
                try:
                    index = int(param_data['vfo_index'])
                    
                    bw = float(param_data['vfo_bw'])
                    
                    if bw == 0 or bw > 2.4e6:
                        return_error_json(s, 1, "Bandwidth error.  Value should be in Hz and not exceed RTLSDR bandwidth")
                        return
                        
                    krakensdr.set_vfo_bandwidth(index, freq)
                    
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            elif s.path.startswith('/api/krakensdr/set_coordinates'):
                param_data = param_data_to_dict(req.query)
                
                if not 'latitude' in param_data.keys() or not 'longitude' in param_data.keys():
                    return_error_json(s, 1, "Correct key not specified in request.  latitude and longitude")
                    return

                try:
                    krakensdr.set_coordinates(index, param_data)
                    
                    return_json_dict(s,  build_base_dict())
                except Exception as e:
                    return_error_json(s, 3, "ERROR setting value: " + str(e))
            else:
                # Catch-all.  Should never be here
                print(get_time_string() + "ERROR: Unknown GET request: " + s.path)
                
                return_error_json(s,  5,  'Unknown request')
        except Exception as e:
            print(get_time_string() + "Unhandled GET exception processing " + s.path + ": " + str(e))
            return_error_json(s,  5,  "Unhandled GET exception: " + str(e))
            
class CustomAgent(object):
    # See https://docs.python.org/3/library/http.server.html
    # For HTTP Server info
    def run(self, port):
        server_address = ('', port)
        try:
            httpd = MultithreadHTTPServer(server_address, AgentRequestHandler)
        except OSError as e:
            curTime = datetime.now()
            print('[' +curTime.strftime("%m/%d/%Y %H:%M:%S") + "] Unable to bind to port " + str(port) +  ". " + e.strerror)
            exit(1)

        curTime = datetime.now()
        print('[' +curTime.strftime("%m/%d/%Y %H:%M:%S") + "] Starting agent on port " + str(port))

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

        httpd.server_close()

        curTime = datetime.now()
        print('[' +curTime.strftime("%m/%d/%Y %H:%M:%S") + "] agent stopped.")

# ----------------- Main -----------------------------
if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='KrakenSDR HTTP Control Agent')
    argparser.add_argument('--port', help='Port for HTTP server to listen on.  Default is 8181.', default=8181, required=False)
    # argparser.add_argument('--html-dir', help='Agent can serve HTML directly.  Just set this to the path of the UI content.  Default=/var/www/html/ase', type=str, default="/var/www/html/ase", required=False)
    argparser.add_argument('--settings-path', help='Path to settings.json.  Default=/home/krakenrf/krakensdr_doa/krakensdr_doa/_share', type=str, default="/home/krakenrf/krakensdr_doa/krakensdr_doa/_share", required=False)
    argparser.add_argument('--allowedips', help="IP addresses allowed to connect to this agent.  Default is any.  This can be a comma-separated list for multiple IP addresses", default='', required=False)
    argparser.add_argument('--debug-http', help="Print each URL request", action='store_true', default=False, required=False)

    args = argparser.parse_args()

    if not os.path.exists(args.settings_path):
        print("ERROR: The specified settings.json path " + args.settings_path + " does not exist. If you know where it is, set it with --settings-path.")
        exit(1)

    try:
        krakensdr = KrakenSDRControl(args.settings_path)
    except:
        print("ERROR: Unable to find settings.json")
        exit(1)
        
    
    debugHTTP = args.debug_http

    port = args.port
    buildAllowedIPs(args.allowedips)

    allowCors = True

    # -------------- Run HTTP Server / Main Loop--------------
    server = CustomAgent()
    server.run(port)
    
