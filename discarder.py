# A script that removes torrents which are dead or very slow from sonarr
# TODO: remove downloads that get stuck on "retrieving metadata"
import os
import shutil
import json
import datetime
import requests
import creds


def delete_from_downloads(download_id, api_base_url, api_key, REQUEST_TIMEOUT=5):
    """Delete movie/series/episode and blacklist from radarr/sonarr based on id."""
    deletion_url = (
        f"{api_base_url}/{download_id}?removeFromClient=true"
        + f"&blocklist=true&apikey={api_key}"
    )
    requests.delete(deletion_url, timeout=REQUEST_TIMEOUT)


def remove_from_local_record(local_record_path, download_id):
    """Remove movie/series from local save file based on download_id"""
    with open(local_record_path, "r", encoding="utf-8") as f:
        saved_items = json.load(f)
    try:
        del saved_items[str(download_id)]
    except KeyError:
        print(f"keyerror for {download_id}.")
        print(f"saved_items: {saved_items}")
    with open(local_record_path, "w", encoding="utf-8") as f:
        json.dump(
            saved_items,
            f,
        )


def add_to_local_record(local_record_path, id, time_monitored):
    """Add download_id:time_last_ok to local record."""
    with open(local_record_path, "r+", encoding="utf-8") as f:
        try:
            monitored_downloads = json.load(f)
        except json.decoder.JSONDecodeError:
            # most likley caused by empty save file.
            monitored_downloads = {}
    monitored_downloads[id] = time_monitored
    with open(local_record_path, "w+", encoding="utf-8") as f:
        json.dump(monitored_downloads, f)


def get_monitored_downloads(local_record_path):
    try:
        with open(local_record_path, "r+") as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                # Most likley caused by empty save file
                return {}
    except FileNotFoundError:
        # Create file and initialize empty dictionary
        with open(local_record_path, "x"):
            return {}


def get_reported_download_queue(
    api_base_url, api_key, radarr, REQUEST_TIMEOUT=5  # radarr är bool
):
    # Get the currently downloading movies from radarr.
    if radarr:
        api_query_url = f"{api_base_url}?pageSize=100&includeUnknownMovieItems=true&includeMovie=true&apikey={api_key}"
    else:
        # TODO inclueseries eller includeepisode?
        api_query_url = f"{api_base_url}?pageSize=100&includeUnknownSeriesItems=true&includeSeries=true&includeEpisode=true&apikey={api_key}"
    api_answer = requests.get(api_query_url, timeout=REQUEST_TIMEOUT).json()
    # The list of current downloading movies is called "records"
    return api_answer["records"]  # TODO: check that api_answer["pages"] < 1


def delete_slow_downloads(
    reported_download_queue,
    local_record_path,
    api_base_url,
    api_key,
    time_left_format="%H:%M:%S",
    default_date_format=r"%Y-%m-%d %H:%M:%S.%f",
    max_allowed_catchup_time=datetime.timedelta(minutes=10),
    max_allowed_download_time=datetime.timedelta(hours=4),
):
    # Loop over movies and check for slow downloads
    monitored_downloads = get_monitored_downloads(local_record_path)

    for download in reported_download_queue:
        download_id = str(download["id"])  # json saves everything as strings.
        # json dump saves everything as strings
        if str(download_id) not in monitored_downloads.keys():
            # We add the download_id to currently downloading movies and continue.
            # Convert datetime object to string so json.dump can save it.
            current_time = datetime.datetime.now().strftime(default_date_format)
            add_to_local_record(local_record_path, download_id, current_time)
            continue
        # Fetch the download time left from the radarr api. For some reason,
        # Radarr does not always report a positive time left, which has to be
        # accounted for by try-except.
        try:
            download_time_left = datetime.datetime.strptime(
                download["timeleft"], time_left_format
            )
            download_time_left = datetime.timedelta(
                hours=download_time_left.hour,
                minutes=download_time_left.minute,
                seconds=download_time_left.second,
            )
            invalid_download_time_reported = False
        except ValueError:
            # A valueerror here likley means that Radarr/Sonarr has sent an invalid
            # Time, which it sometimes does when a download is stalled.
            # We treat this like the torrent is stalled.
            invalid_download_time_reported = True

        except KeyError:
            # a KeyError here likely means that the download has stalled.
            invalid_download_time_reported = True
        # Convert download_time_left to a timedelta:

        if (
            invalid_download_time_reported
            or download_time_left > max_allowed_download_time
            or download_time_left == datetime.timedelta(seconds=0)
        ):
            # If download time left is 0 that means the download has stalled.
            # Create datetime object from saved string
            time_last_monitored = datetime.datetime.strptime(
                monitored_downloads[download_id], default_date_format
            )
            time_since_download_slowed = datetime.datetime.now() - time_last_monitored
            if time_since_download_slowed > max_allowed_catchup_time:
                # The movie has not caught up with max allowed time in five minutes
                # and is to be discarded
                print(f"deleting download {download_id}")
                delete_from_downloads(download_id, api_base_url, api_key)
                remove_from_local_record(local_record_path, download_id)
            else:
                # The download is slow but it has time left to catch up.
                continue
        else:
            # If the download suddenly slows down it should have MAX_CATCHUP_TIME
            # to catch up, so we update the last_monitored_time to match the
            # current time.
            current_time = datetime.datetime.now().strftime(default_date_format)
            add_to_local_record(local_record_path, download_id, current_time)


def delete_removed_monitored_movies(reported_download_queue, local_record_path):
    # Go through the save file and check for movies that are monitored but not
    # in the Radarr que.
    monitored_downloads = get_monitored_downloads(local_record_path)
    monitored_downloads_ids = [int(id) for id in monitored_downloads.keys()]
    download_ids = [int(download["id"]) for download in reported_download_queue]
    for monitored_download_id in monitored_downloads_ids:
        if monitored_download_id not in download_ids:
            remove_from_local_record(local_record_path, monitored_download_id)


def generate_api_base_url(host, port):
    api_base_url = f"http://{host}:{port}/api/v3/queue"
    return api_base_url


if __name__ == "__main__":
    # radarr
    local_record_path = r"currently_downloading_movies.json"
    api_base_url = generate_api_base_url(creds.radarr_host, creds.radarr_port)
    reported_download_queue = get_reported_download_queue(
        api_base_url, creds.radarr_api_key, radarr=True
    )
    delete_slow_downloads(
        reported_download_queue,
        local_record_path,
        api_base_url,
        api_key=creds.radarr_api_key,
    )
    delete_removed_monitored_movies(reported_download_queue, local_record_path)

    # sonarr
    local_record_path = r"currently_downloading_series.json"
    api_base_url = generate_api_base_url(creds.sonarr_host, creds.sonarr_port)
    reported_download_queue = get_reported_download_queue(
        api_base_url, creds.sonarr_api_key, radarr=False
    )
    delete_slow_downloads(
        reported_download_queue,
        local_record_path,
        api_base_url,
        api_key=creds.sonarr_api_key,
    )
    delete_removed_monitored_movies(reported_download_queue, local_record_path)
