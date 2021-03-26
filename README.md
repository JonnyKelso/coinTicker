# coinTicker
A little bot that periodically reads current price data from Binance, tracks current profit.
This bot does not make any trades, it just reads prices and displays balances for your account, if any :) 

Requires Binance API, and Discord API for notifications though that can be disabled.
Requires a Binance API key in a file 'config.py'. Create a Binance account at https://www.binance.com/, then go to Account -> Settings -> API Management, create and copy the API key + secret to config.py as API_KEY and API_SECRET.
Note it is stronly recommended to change the restrictions on your API key to only alolow read only operations - disallow trades if you're not going to be trading using the key - and restrict the usage of the API key to your own IP address, and set up 2FA for your account. Obviously choose strong accopunt password.
Requires a Discord webhook URL. Create a discord channel, got to Server Settings -> Integrations -> Webhooks -> New Webhook, give it a name and copy the URL, save it alongside the Binanace API key as 'DISCORD_WEBHOOK_URL'


