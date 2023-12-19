
# Torrent discarder for Radarr

This is a script for discarding dead/slow torrents from the Radarr queue.

## Running the script

Download torrent_discarder.py and create a text file called `info.txt` with two lines -
 your Radarr api key and your radarr server's ip-address.

Run the script every few minutes to check for dead torrents. (For example using Crontab)
