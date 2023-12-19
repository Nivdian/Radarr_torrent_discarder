# A script that removes torrents which are dead or very slow from radarr.
# This script is heavily inspired by a javascript program by u/Douglas96
# (see https://www.reddit.com/r/radarr/comments/101q31k/i_wrote_a_script_that_replaces_slowdead_torrents/)

import json
import datetime
import requests

# Format Radarr uses to display time left of download
time_left_format = "%H:%M:%S"
# Define format to save dates in json
default_date_format = r"%Y-%m-%d %H:%M:%S.%f" 
# Time allowed for a movie to download
MAX_ALLOWED_DOWNLOAD_TIME = datetime.timedelta(hours=2)
# Time allowed for a movie to catch up to the allowed download time
MAX_CATCHUP_TIME = datetime.timedelta(minutes=5)

# Generate a url that queries the radarr api for movies currently downloading.
with open("info.txt") as f:
    lines = f.readlines()
    RADARR_API_KEY = lines[0].strip() # includes \n without strip()
    RADARR_URL = lines[1].strip()
base_url = RADARR_URL + "/api/v3/queue"
query_arguments = "?includeUnknownMovieItems=true&includeMovie=true"
api_key_argument = f"&apikey={RADARR_API_KEY}"
api_query_url = base_url + query_arguments + api_key_argument

def delete_from_radarr_downloads(download_id):
    """Delete movie and blacklist from radarr based on movie_id."""
    deletion_url = (f"{base_url}/{download_id}?removeFromClient=true"
                    + f"&blocklist=true{api_key_argument}")
    requests.delete(deletion_url)

def remove_from_script_record(script_record_path, download_id):
    """Remove movie from local save file based on download_id"""
    with open(script_record_path,"r",encoding="utf-8") as f:
        saved_movies = json.load(f)
    del saved_movies[download_id]
    with open(script_record_path,"w",encoding="utf-8") as f:
        json.dump(saved_movies,f,)

def add_to_script_record(script_record_path,
        download_id, time_monitored):
    """Add download_id:time_monitored to script_record_path."""
    with open(script_record_path,"r+",encoding="utf-8") as f:
        try:
            monitored_downloads = json.load(f)
        except json.decoder.JSONDecodeError:
            # most likley caused by empty save file.
            monitored_downloads = {}
    monitored_downloads[download_id] = time_monitored
    with open(script_record_path,"w+",encoding="utf-8") as f:
        json.dump(monitored_downloads,f)


# Load the already seen downloading movies.
monitored_downloads_path = r"currently_downloading_movies.json"
try:
    with open(monitored_downloads_path, "r+") as f:
        try:
            monitored_downloads = json.load(f)
        except json.decoder.JSONDecodeError:
            # Most likley caused by empty save file
            monitored_downloads = {}
except FileNotFoundError:
    # Create file and initialize empty dictionary
    open(monitored_downloads_path,"x")
    monitored_downloads = {}

# Get the currently downloading movies from radarr.
api_answer = requests.get(api_query_url).json()
# The list of current downloading movies is called "records"
radarr_downloads = api_answer["records"] #TODO: check that api_answer["pages"] < 1

# Loop over movies and check for slow downloads
for radarr_download in radarr_downloads:
    radarr_download_id = str(radarr_download['id']) # json saves everything as strings.
    # json dump saves everything as strings
    if str(radarr_download_id) not in monitored_downloads.keys():
        # We add the download_id to currently downloading movies and continue.
        # Convert datetime object to string so json.dump can save it.
        current_time = datetime.datetime.now().strftime(default_date_format) 
        add_to_script_record(monitored_downloads_path,
                             radarr_download_id, current_time)
        continue
    download_time_left = datetime.datetime.strptime(radarr_download["timeleft"],
                                                    time_left_format)
    # Convert download_time_left to a timedelta:
    download_time_left = datetime.timedelta(hours=download_time_left.hour,
                                            minutes=download_time_left.minute,
                                            seconds=download_time_left.second)
    if (download_time_left > MAX_ALLOWED_DOWNLOAD_TIME):
        # Load datetime object from saved string
        time_last_monitored = datetime.datetime.strptime(
            monitored_downloads[radarr_download_id],
            default_date_format)
        time_since_download_slowed = (datetime.datetime.now()
            - time_last_monitored)
        if time_since_download_slowed > MAX_CATCHUP_TIME:
            # The movie has not caught up with max allowed time in five minutes
            # and is to be discarded
            delete_from_radarr_downloads(radarr_download_id)
            remove_from_script_record(monitored_downloads_path,
                                      radarr_download_id)
        else:
            # The download is slow but it has time left to catch up.
            continue 
    else:
        # If the download suddenly slows down it should have MAX_CATCHUP_TIME 
        # to catch up, so we update the time 
        # Convert current time to string to save with json.dump
        current_time = datetime.datetime.now().strftime(default_date_format)

        add_to_script_record(monitored_downloads_path,
                             radarr_download_id, current_time)

# Delete monitored download_id:s that are not being downloaded. 
radarr_download_ids = [download["id"] for download in radarr_downloads]
for download_id in monitored_downloads:
    if download_id not in radarr_download_ids:
        remove_from_script_record(monitored_downloads_path,download_id)
