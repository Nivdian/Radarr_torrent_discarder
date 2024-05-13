# A script that removes torrents which are dead or very slow from radarr.
# This script is heavily inspired by a javascript program by u/Douglas96
# (see https://www.reddit.com/r/radarr/comments/101q31k/i_wrote_a_script_that_replaces_slowdead_torrents/)
# TODO: add check for if time left stays at 00:00 (means that torrent is dead.)
# TODO: remove downloads that get stuck on "retrieving metadata"
import os
import shutil
import json
import datetime
import requests
import creds


def delete_from_radarr_downloads(
    download_id, api_base_url, radarr_api_key, REQUEST_TIMEOUT=5
):
    """Delete movie and blacklist from radarr based on movie_id."""
    deletion_url = (
        f"{api_base_url}/{download_id}?removeFromClient=true"
        + f"&blocklist=true&apikey={radarr_api_key}"
    )
    requests.delete(deletion_url, timeout=REQUEST_TIMEOUT)


def remove_from_script_record(script_record_path, download_id):
    """Remove movie from local save file based on download_id"""
    with open(script_record_path, "r", encoding="utf-8") as f:
        saved_movies = json.load(f)
    del saved_movies[download_id]
    with open(script_record_path, "w", encoding="utf-8") as f:
        json.dump(
            saved_movies,
            f,
        )


def add_to_script_record(script_record_path, download_id, time_monitored):
    """Add download_id:time_last_ok to script_record_path."""
    with open(script_record_path, "r+", encoding="utf-8") as f:
        try:
            monitored_downloads = json.load(f)
        except json.decoder.JSONDecodeError:
            # most likley caused by empty save file.
            monitored_downloads = {}
    monitored_downloads[download_id] = time_monitored
    with open(script_record_path, "w+", encoding="utf-8") as f:
        json.dump(monitored_downloads, f)


def get_monitored_downloads(monitored_downloads_path):
    try:
        with open(monitored_downloads_path, "r+") as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                # Most likley caused by empty save file
                return {}
    except FileNotFoundError:
        # Create file and initialize empty dictionary
        with open(monitored_downloads_path, "x"):
            return {}


def get_radarr_reported_downloads(
    api_base_url,
    radarr_api_key,
    REQUEST_TIMEOUT=5,  # seconds
):
    # Get the currently downloading movies from radarr.
    api_query_url = f"{api_base_url}?includeUnknownMovieItems=true&includeMovie=true&apikey={radarr_api_key}"
    api_answer = requests.get(api_query_url, timeout=REQUEST_TIMEOUT).json()
    # The list of current downloading movies is called "records"
    return api_answer["records"]  # TODO: check that api_answer["pages"] < 1


def delete_slow_downloads(
    radarr_reported_downloads,
    monitored_downloads,
    time_left_format="%H:%M:%S",
    default_date_format=r"%Y-%m-%d %H:%M:%S.%f",
    max_allowed_catchup_time=datetime.timedelta(minutes=10),
    max_allowed_download_time=datetime.timedelta(hours=4),
):
    # Loop over movies and check for slow downloads
    for radarr_download in radarr_reported_downloads:
        radarr_download_id = str(
            radarr_download["id"]
        )  # json saves everything as strings.
        # json dump saves everything as strings
        if str(radarr_download_id) not in monitored_downloads.keys():
            # We add the download_id to currently downloading movies and continue.
            # Convert datetime object to string so json.dump can save it.
            current_time = datetime.datetime.now().strftime(default_date_format)
            add_to_script_record(
                monitored_downloads_path, radarr_download_id, current_time
            )
            continue
        # Fetch the download time left from the radarr api. For some reason,
        # Radarr does not always report a positive time left, which has to be
        # accounted for by try-except.
        try:
            download_time_left = datetime.datetime.strptime(
                radarr_download["timeleft"], time_left_format
            )
            download_time_left = datetime.timedelta(
                hours=download_time_left.hour,
                minutes=download_time_left.minute,
                seconds=download_time_left.second,
            )
            radarr_reports_invalid_download_time = False
        except ValueError:
            # A valueerror here likley means that Radarr has sent an invalid
            # Time, which it sometimes does when a download is stalled.
            # We treat this like the torrent is stalled.
            radarr_reports_invalid_download_time = True

        # Convert download_time_left to a timedelta:
        if (
            download_time_left > max_allowed_download_time
            or download_time_left == datetime.timedelta(seconds=0)
            or radarr_reports_invalid_download_time
        ):
            # If download time left is 0 that means the download has stalled.
            # Create datetime object from saved string
            time_last_monitored = datetime.datetime.strptime(
                monitored_downloads[radarr_download_id], default_date_format
            )
            time_since_download_slowed = datetime.datetime.now() - time_last_monitored
            if time_since_download_slowed > max_allowed_catchup_time:
                # The movie has not caught up with max allowed time in five minutes
                # and is to be discarded
                delete_from_radarr_downloads(radarr_download_id)
                remove_from_script_record(monitored_downloads_path, radarr_download_id)
            else:
                # The download is slow but it has time left to catch up.
                continue
        else:
            # If the download suddenly slows down it should have MAX_CATCHUP_TIME
            # to catch up, so we update the last_monitored_time to match the
            # current time.
            current_time = datetime.datetime.now().strftime(default_date_format)
            add_to_script_record(
                monitored_downloads_path, radarr_download_id, current_time
            )


def delete_removed_monitored_movies(
    radarr_reported_downloads,
    monitored_downloads_path=r"currently_downloading_movies.json",
):
    # Go through the save file and check for movies that are monitored but not
    # in the Radarr que. Wait for wait_time_before_deletion and then delete the
    # movie.
    radarr_download_ids = [download["id"] for download in radarr_reported_downloads]
    for monitored_download_id in monitored_downloads:
        if monitored_download_id not in radarr_download_ids:
            remove_from_script_record(monitored_downloads_path, monitored_download_id)


def generate_api_base_url(radarr_host, radarr_port):
    api_base_url = f"http://{radarr_host}:{radarr_port}/api/v3/queue"
    return api_base_url


if __name__ == "__main__":
    monitored_downloads_path = r"currently_downloading_movies.json"
    monitored_downloads = get_monitored_downloads(monitored_downloads_path)

    api_base_url = generate_api_base_url(creds.host, creds.port)
    radarr_reported_downloads = get_radarr_reported_downloads(
        api_base_url, creds.radarr_api_key
    )

    delete_slow_downloads(radarr_reported_downloads, monitored_downloads)
    delete_removed_monitored_movies(radarr_reported_downloads)
