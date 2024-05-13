# ibland finns ingen metadata.
# Då dyker den upp i historiken men inte i queue.

import json
import datetime
import requests
import creds
from transmission_rpc import Client
import time

# workflow: kollar i transmission
# om någon är trasig, kolla dess hash
# kolla i history för sonarr
# om någon har download_id med samma hash: ta dess id
# markera id som failed
#


def get_torrent_id_from_hash(
    torrent_hash, radarr, api_base_url, api_key, request_timeout=5
):
    if radarr:
        api_history_query_url = (
            f"{api_base_url}?pageSize=100&includeMovie=true&apikey={api_key}"
        )
    else:
        api_history_query_url = f"{api_base_url}?pageSize=100&includeSeries=true&includeEpisode=true&apikey={api_key}"

    history = requests.get(api_history_query_url, timeout=request_timeout).json()
    for item in history["records"]:
        if item["downloadId"].lower() == torrent_hash.lower():
            return item["id"]
    raise ValueError(f"No item with hash {torrent_hash} found in history.")


def mark_torrent_as_failed_from_id(
    torrent_id, api_base_url, api_key, request_timeout=5
):
    api_history_failed_post_url = f"{api_base_url}/failed/{torrent_id}?apikey={api_key}"
    requests.post(api_history_failed_post_url, timeout=request_timeout)


def mark_torrent_as_failed_from_hash(torrent_hash, radarr, api_base_url, api_key):
    torrent_id = get_torrent_id_from_hash(
        torrent_hash=torrent_hash,
        radarr=radarr,
        api_base_url=api_base_url,
        api_key=api_key,
    )
    mark_torrent_as_failed_from_id(
        torrent_id, api_base_url=api_base_url, api_key=api_key
    )

    # TODO radera från transmission också!


def get_previous_torrents_without_metadata(local_record_path):
    try:
        with open(local_record_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def get_torrents_without_metadata(client):
    torrents_without_metadata = {}
    for torrent in client.get_torrents():
        if torrent.metadata_percent_complete < 1:
            torrents_without_metadata[torrent.hashString] = time.time()
    return torrents_without_metadata


def save_torrents_without_metadata(torrents_without_metadata, local_record_path):
    with open(local_record_path, "w") as f:
        json.dump(torrents_without_metadata, f)


def remove_from_local_record(local_record_path, torrent_hash):
    with open(local_record_path, "r", encoding="utf-8") as f:
        saved_items = json.load(f)
    try:
        del saved_items[str(torrent_hash)]
    except KeyError:
        print(f"keyerror for {torrent_hash}.")
        print(f"saved_items: {saved_items}")
    with open(local_record_path, "w", encoding="utf-8") as f:
        json.dump(
            saved_items,
            f,
        )


def remove_torrents_with_metadata(
    torrents_without_metadata, previous_torrents_without_metadata, local_record_path
):
    # om en torrent har metadata nu, ta bort den från listan
    for torrent_hash in previous_torrents_without_metadata:
        if torrent_hash not in torrents_without_metadata:
            remove_from_local_record(local_record_path, torrent_hash)


def search_and_mark_torrents_without_metadata(
    torrents_without_metadata,
    previous_torrents_without_metadata,
    radarr,
    api_base_url,
    api_key,
    transmission_client,
    time_allowed_without_metadata=1 * 60,
):
    # ta bort torrents som har varit utan metadata för länge
    for torrent_hash in torrents_without_metadata:
        if torrent_hash in previous_torrents_without_metadata:
            metadata_download_start = previous_torrents_without_metadata[torrent_hash]
            current_time = torrents_without_metadata[torrent_hash]
            if current_time - metadata_download_start > time_allowed_without_metadata:
                mark_torrent_as_failed_from_hash(
                    torrent_hash,
                    radarr=radarr,
                    api_base_url=api_base_url,
                    api_key=api_key,
                )
                transmission_client.remove_torrent(torrent_hash)
            else:
                torrents_without_metadata[torrent_hash] = metadata_download_start


if __name__ == "__main__":
    client = Client(
        host=creds.transmission_host,
        port=creds.transmission_port,
        username=creds.transmission_username,
        password=creds.transmission_password,
    )

    local_record_path = r"torrents_without_metadata.json"
    api_history_base_url = (
        f"http://{creds.sonarr_host}:{creds.sonarr_port}/api/v3/history"
    )
    torrents_without_metadata = get_torrents_without_metadata(client)
    previous_torrents_without_metadata = get_previous_torrents_without_metadata(
        local_record_path
    )

    # sonarr
    search_and_mark_torrents_without_metadata(
        torrents_without_metadata=torrents_without_metadata,
        previous_torrents_without_metadata=previous_torrents_without_metadata,
        radarr=False,
        api_base_url=api_history_base_url,
        api_key=creds.sonarr_api_key,
        transmission_client=client,
    )
    remove_torrents_with_metadata(
        torrents_without_metadata=torrents_without_metadata,
        previous_torrents_without_metadata=previous_torrents_without_metadata,
        local_record_path=local_record_path,
    )
    save_torrents_without_metadata(
        torrents_without_metadata, local_record_path=local_record_path
    )

    # radarr
    local_record_path = r"torrents_without_metadata.json"
    api_history_base_url = (
        f"http://{creds.radarr_host}:{creds.radarr_port}/api/v3/history"
    )
    torrents_without_metadata = get_torrents_without_metadata(client)
    previous_torrents_without_metadata = get_previous_torrents_without_metadata(
        local_record_path
    )

    search_and_mark_torrents_without_metadata(
        torrents_without_metadata=torrents_without_metadata,
        previous_torrents_without_metadata=previous_torrents_without_metadata,
        radarr=True,
        api_base_url=api_history_base_url,
        api_key=creds.radarr_api_key,
        transmission_client=client,
    )
    remove_torrents_with_metadata(
        torrents_without_metadata=torrents_without_metadata,
        previous_torrents_without_metadata=previous_torrents_without_metadata,
        local_record_path=local_record_path,
    )
    save_torrents_without_metadata(
        torrents_without_metadata, local_record_path=local_record_path
    )
