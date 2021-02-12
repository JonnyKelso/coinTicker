# coinTicker
A little bot that periodically reads current price data from Binance, tracks current profit and prints a little marker to screen to show price movement

Requires Binance API, and Discord API for notifications though that can be disabled.
Requires a Binance API key in a file 'config.py'. Create a Binance account at https://www.binance.com/, then go to Account -> Settings -> API Management, create and copy the API key + secret to config.py as API_KEY and API_SECRET.
Requires a Discord webhook URL. Create a discord channel, got to Server Settings -> Integrations -> Webhooks -> New Webhook, give it a name and copy the URL, save it alongside the Binanace API key as 'DISCORD_WEBHOOK_URL'


