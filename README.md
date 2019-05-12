# Google Cloud Dynamic DNS Client

This is a simple dynamic DNS script for Google Cloud DNS. The script will check for its public IP address, and then based on its configuration it read from the configuration file, check whether Google Cloud DNS has a corresponding DNS entry. If no corresponding entry is found, the script will create one. If a corresponding entry is found, but has an IP address which doesn't match that of what the script found, then the script will update then Google Cloud entry (read delete, then create). Finally, if the scripts configuration file matches that of the Google Cloud DNS entry, then it will sleep for an interval of x, and the process repeats.

This project consists of the following components:

- **gcloud-ddns.py**: the dynamic dns client script
- **ddns-conf.json**: programs configuration file
- **requirements.txt**: requirements to be installed
## Requirements
This script requires **Python 3.6 or greater**. f-strings are extensively used. Package requirements are listed in [requirements.txt](requirements.txt)
## Usage
```bash
Usage: python gcloud-ddns.py [path_to_configuration_file.json]
```
## Setup
```bash
$ git clone git@github.com:conorcunningham/google-ddns.git
$ cd google-ddns
$ python3 gcloud-ddns.py
```
The script will run in the foreground. I'm going to play around with it and test it to see if it can run reliably as a service.
## Configuration file
The configuration for the script is read from a json file. Here are the contents of the example [ddns-conf.json](ddns-config.json) file
``` json
{
  "host": "firewall.example.com.",
  "project_id": "fluffy-penguin-242411",
  "managed_zone": "example",
  "domain": "example.com",
  "ttl": 60,
  "interval": 600,
  "api-key": "./ddns-api-key.json",
  "log-path": "./ddns.log"
}
```
The script accepts one optional CLI argument which is the path to the configuration file. If none is given, the script will look for ```ddns-config.json``` in the same directory as the script.


- **host**: the fully-qualified domain name of the host you want to set. *_NB_** You must include the . after the .com. This is a Google requirement/
- **project_id**: Your project ID within Google Cloud
- **managed_zone**: The name of your managed zone in Google Cloud
- **domain**: Your domain name
- **ttl**: The number of seconds for the TTL
- **interval**: How long the script will sleep before running again
- **api-key**: Path to the API key in JSON format
- **log-path**: Path to the logfile

## Authentication 
In order to use the Google Cloud API, you will need an API key for your account. This key will be a json file and must be configured in the configuration file.

The script will set ```GOOGLE_APPLICATION_CREDENTIALS``` environmental variable to the path of your API key and Google's modules will use this environmental variable to handle authentication.

```python        
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = api_key
```
## ipify.org API
This project makes use of the snazzy [ipify.org](https://www.ipify.org) API for fetching the clients public IP address.

## TODO
Migrate print() statements to better logging, i.e. to a file and add datetime output with the log entries.