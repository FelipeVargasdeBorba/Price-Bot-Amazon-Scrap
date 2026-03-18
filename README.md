# 📦 Amazon Price Monitor (Discord Bot)

A simple Amazon price monitoring project built with Python and a Discord bot.

## 🚀 Technologies
- Python  
- discord.py  
- SerpApi (used to bypass limitations of traditional scraping)

## ⚙️ How it works
- The user sends an Amazon product to the bot  
- The bot monitors the price using SerpApi  
- When the price changes, the bot sends a message on Discord with the update  

## ⚠️ Note
Direct scraping from Amazon was not used due to blocking and limitations, so SerpApi was required.

## 🔄 Future improvements
- Implement automatic updates every 5 hours with all monitored items  
- Better handling of multiple products  
- Data persistence  
