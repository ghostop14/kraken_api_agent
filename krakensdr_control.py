#!/usr/bin/env python3
import os
import json

# This class is really just a bridge to the settings.json file. 
# KrakenSDR monitors this file for changes and updates.  You'll notice that any UI changes are reflected in this file.
#

class KrakenSDRControl(object):
    def __init__(self, settings_dir="/home/krakenrf/krakensdr_doa/krakensdr_doa/_share"):
        self.settings_dir = settings_dir
        self.settings_file = self.settings_dir + "/settings.json"

        self.settings = None
        
        if not os.path.exists(self.settings_file):
            raise Exception("ERROR: Unable to find settings.json at " + self.settings_file)
            
        self.valid_gains = [0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6]
        
    def get_config(self):
        with open(self.settings_file, 'r') as f:
            settings = json.load(f)

        return settings
        
    def save_config(self,new_config):
        with open(self.settings_file, "w") as file:
            json.dump(new_config, file, indent=4)
        
    def update_value(self,key, new_value, save_file=True):
        # Generic key/value update
        
        # If we're not saving the file, work with cached values till we save
        if self.settings is None:
            settings = self.get_config()
        else:
            settings = self.settings
            
        settings[key] = new_value
        
        if save_file:
            self.save_config(settings)
            self.settings = None
        else:
            # Save for more updates
            self.settings = settings
            
    def optimize_short_bursts(self,new_state, save_file=True):
        self.update_value('en_optimize_short_bursts', new_state, save_file)
        
    def set_frequency(self,new_frequency_mhz, save_file=True):
        self.update_value('center_freq', new_frequency_mhz, save_file)
        
    def set_output_vfo(self,vfo_number, vfo, save_file=True):
        self.update_value('output_vfo', vfo, save_file)
        
    def set_vfo_frequency(self,vfo_number, frequency, save_file=True):
        key = "vfo_freq_" + str(vfo_number)
        
        self.update_value(key, frequency, save_file)
        
    def set_vfo_bandwidth(self,vfo_number, bw, save_file=True):
        key = "vfo_bw_" + str(vfo_number)
        
        self.update_value(key, bw, save_file)
        
    def set_gain(self,gain, save_file=True):
        if gain not in self.valid_gains:
            raise Exception("ERROR: Invalid gain value.  Gain must be one of " + str(self.valid_gains))
            
        self.update_value('uniform_gain', gain, save_file)
    
    def set_coordinates(self,coordinates):
        # Coordinates should have keys latitude, longitude
        
        settings = self.get_config()
        
        settings['latitude'] = float(coordinates['latitude'])
        settings['longitude'] = float(coordinates['longitude'])
        
        if 'heading' in coordinates:
            settings['heading'] = float(coordinates['heading'])
            
        if 'location_source' in coordinates:
            settings['location_source'] = coordinates['location_source']
            
        if 'gps_fixed_heading' in coordinates:
            settings['gps_fixed_heading'] = coordinates['gps_fixed_heading']
            
        if 'gps_min_speed' in coordinates:
            settings['gps_min_speed'] = int(coordinates['gps_min_speed'])
            
        if 'gps_min_speed_duration' in coordinates:
            settings['gps_min_speed_duration'] = int(coordinates['gps_min_speed_duration'])
            
        self.save_config(settings)
        
