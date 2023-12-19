
# Torrent discarder for Radarr

This is a script for discarding dead/slow torrents from the Radarr queue.

## Running the script

Download torrent_discarder.py and replace `MAX_ALLOWED_DOWNLOAD_TIME`,
`MAX_CATCHUP_TIME`, `RADARR_URL` and create a text file called `apikey.txt` with your Radarr api key.

Run the script every few minutes to check for dead torrents. (For example using Crontab)
