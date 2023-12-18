# A script that removes torrents which are dead or very slow from radarr.
# This script is heavily inspired by a javascript program by u/Douglas96
# (see https://www.reddit.com/r/radarr/comments/101q31k/i_wrote_a_script_that_replaces_slowdead_torrents/)

import json
import datetime
import requests


time_left_format = "%H:%M:%S"
# Time allowed for a movie to download
MAX_ALLOWED_DOWNLOAD_TIME = datetime.datetime.strptime("2:0:0",time_left_format)
# Time allowed for a movie to catch up to the allowed download time
MAX_CATCHUP_TIME = datetime.datetime.strptime("0:5:0",time_left_format)

# Generate a url that queries the radarr api for movies currently downloading.
with open("apikey.txt") as f:
    RADARR_API_KEY = f.readlines()[0]
RADARR_URL = "http://192.168.1.152:7878"
base_url = RADARR_URL + "/api/v3/queue"
query_arguments = "?includeUnknownMovieItems=true&includeMovie=true"
api_key_argument = f"&apikey={RADARR_API_KEY}"
api_query_url = base_url + query_arguments + api_key_argument

def delete_movie_from_radarr_downloads(movie_id):
    """Delete movie and blacklist from radarr based on movie_id."""
    deletion_url = (f"{base_url}/{movie_id}?removeFromClient=true"
                    + f"&blocklist=true{api_key_argument}")
    requests.delete(deletion_url)


def remove_movie_from_script_record(script_record_path, movie_id):
    """Remove movie from currently_downloading.json based on movie_id."""
    with open(script_record_path,"r",encoding="utf-8") as f:
        saved_movies = json.load(f)
    del saved_movies[movie_id]
    with open(script_record_path,"w",encoding="utf-8") as f:
        json.dump(saved_movies)

# Now we load the already seen downloaded movies
currently_downloading_movies_path = r"currently_downloading_movies.json"
with open(currently_downloading_movies_path, "r+") as f:
    currently_downloading_movies = json.load(f)

api_answer = requests.get(api_query_url).json()
# The list of current downloading movies is called "records"
for movie in api_answer["records"]:
    movie_id = movie['id']
    time_left = datetime.date.strptime(movie["timeleft"],time_left_format)
    if (time_left > MAX_ALLOWED_DOWNLOAD_TIME 
            and movie_id in currently_downloading_movies):
        if (currently_downloading_movies[movie_id]["time_monitored"] 
                > MAX_CATCHUP_TIME):
            delete_movie_from_radarr_downloads(movie_id)
            remove_movie_from_script_record(currently_downloading_movies_path,
                                            movie_id)

            # The movie has not caught up with max allowed time in five minutes
            # and is to be discarded





print(api_answer["records"][0]["movieId"])
