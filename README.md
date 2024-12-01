# KrakenSDR HTTP API Agent

## Overview

This simple python agent runs an HTTP listener on port 8181 and provides an HTTP API bridge to control KrakenSDR via settings.json file updates.  KrakenSDR relies on settings.json file changes to monitor for all control functions such as frequency and gain changes, and VFO control  This agent provides basic HTTP call capability once KrakenSDR is running to have some programatic operational control over tuning and getting current results in JSON format.

This agent is only designed to supplement all primary configuration done in the KrakenSDR UI.  Specifically to allow basic external programatic control.

NOTE: When issuing configuration change commands that trigger a recalibration, you should allow KrakenSDR about 8 seconds (may take some experimentation) to go through the calibration process.  There's nothing the bridge can do about that recalibration time as it's a KrakenSDR function that has to happen.

## Prerequisites

``
sudo apt install python3-tzlocal
``

IMPORTANT: 

This API agent does not completely replace the KrakenSDR UI.  All core settings such as array setup, etc. should still be done there.

Also NOTE: From the KrakenSDR UI, "Start Processing" should already be running, and you should make sure that everything is functioning properly.  This agent only give operational query/control of the settings.json file and is not a substitute for the standard UI.

## Setup

These instructions are for the krakensdr raspberry pi image.  If you adjust the location, you will need to adjsut the service install file to point to the correct path.

### Clone repository

Either from the KrakenSR system, or locally to then copy to the KrakenSDR, clone the repository to /home/krakenrf/kraken_api_agent:

```
    <log in to krakensdr raspberry pi image as default krakenrf>
    cd $HOME
    git clone https://github.com/ghostop14/kraken_api_agent.git
```

## Service Setup

cd into the /home/krakenrf/kraken_api_agent/systemctl_service directory and run:

```
    sudo ./install_service.sh
```

The service will be called krakensdragent (systemctl status krakensdragent)

## Troubleshooting

You can check that the service is running after installation with:

```
sudo systemctl status krakensdragent
```

And you can check that it is listening with:

```
sudo netstat -auntp | grep ":8181"
```

If it looks like the service did not start, cd into /home/krakenrf/kraken_api_agent and run:

```
sudo ./kraken_api_agent.py
```

Any errors there should indicate where to look for any problems (e.g. missing python modules)

## GET API Calls

### http://<system>:8181/api/krakensdr/get_config

**Parameters**: None

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
    "settings": {<settings.json file content>}
}
```

### http://<system>:8181/api/krakensdr/get_doa

This function bridges the http://<system>:8081/DOA_value.html call that returns CSV data, converts it to JSON and returns it in the response dictionary.

**Parameters**: None

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
    "doa_info": {<DoA CSV converted to a JSON dictionary>}
}
```

### http://<system>:8181/api/krakensdr/set_frequency_and_vfo

**NOTES:** 

- Each API call to update the file may trigger a resync.  This API allows the radio frequency and VFO of interest to be set in a single call to avoid unnecessary updates.
- Note that freq is in MHZ and vfo_freq is in Hz (this is just the way they are in the config file)

**Parameters**: 

freq=frequency in MHz  # This represents the tuning frequency of the radios

vfo_index=index

vfo_freq=frequency in Hz

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_frequency_and_vfo?freq=467&vfo_index=0&vfo_freq=46737700
```

### http://<system>:8181/api/krakensdr/set_frequency
**Parameters**: 
freq=frequency in MHz  # This represents the tuning frequency of the radios

[optional] gain=gain

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_frequency?freq=467
```

### http://<system>:8181/api/krakensdr/set_gain

**Notes:**
Valid gains are: 0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6


**Parameters**: 
gain=gain

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_gain?gain=16.6
```

### http://<system>:8181/api/krakensdr/set_output_vfo
**Parameters**: 
vfo_index=index

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_output_vfo?vfo_index=0
```

### http://<system>:8181/api/krakensdr/en_optimize_short_bursts
**Parameters**: 
state=[true | false]

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/en_optimize_short_bursts?state=true
```

### http://<system>:8181/api/krakensdr/set_vfo_frequency
**Parameters**: 
vfo_index=index

vfo_freq=frequency in Hz

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_vfo_frequency?vfo_index=0&vfo_freq=467000000
```

### http://<system>:8181/api/krakensdr/set_vfo_bandwidth
**Parameters**: 
vfo_index=index

vfo_bw=bandwidth in Hz

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_vfo_bandwidth?vfo_index=0&vfo_bw=12500
```

### http://<system>:8181/api/krakensdr/set_coordinates

set_coordinates provides access to the latitude, longitude, and GPS keys in the configuration file for manual control.

**Parameters**: 
latitude=lat

longitude=lon

The following values are available but optional:
heading, location_source, gps_fixed_heading, gps_min_speed, gps_min_speed_duration

**Returns**: JSON dictionary with the following keys: 
```
{
    "errcode": 0,  # Or > 0 for error 
    "errmsg": "", # If errcode > 0, an error description will be present.
}
```

**Command-line example:**
```
curl http://localhost:8181/api/krakensdr/set_coordinates?latitude=0.l0&longitude=0.0
```


