
# Torrent discarder for Radarr

This is a script for discarding dead/slow torrents from the Radarr queue.

## Running the script

Download torrent_discarder.py and create a text file called `info.txt` with two
 or three lines:

- Your Radarr api key
- Your radarr server's ip-address (e.g. `https://127.0.0.1:7878`)
- (Optional) The local download path

Run the script every few minutes to check for dead torrents. (For example using Crontab)
