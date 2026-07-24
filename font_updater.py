import os
import re
import ast

mapping = {
    'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑', 'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
}

def translate_str(text):
    res = []
    in_tag = False
    in_var = False
    for i, char in enumerate(text):
        if char == '<': in_tag = True
        elif char == '>': in_tag = False; res.append(char); continue
        elif char == '{': in_var = True
        elif char == '}': in_var = False; res.append(char); continue
        
        if not in_tag and not in_var and char in mapping:
            res.append(mapping[char])
        else:
            res.append(char)
    return "".join(res)

files = [
    '/home/ubuntu/Numbott_Telethon/utils/keyboards.py',
    '/home/ubuntu/Numbott_Telethon/plugins/start.py',
    '/home/ubuntu/Numbott_Telethon/plugins/profile.py',
    '/home/ubuntu/Numbott_Telethon/plugins/deposit.py',
    '/home/ubuntu/Numbott_Telethon/plugins/buy.py',
    '/home/ubuntu/Numbott_Telethon/plugins/admin.py'
]

# We will apply translation to visible texts. We know they are inside f"..." or "..." and usually contain bold <b> tags or emojis.
# A simpler regex approach to replace literal text in strings without breaking python code:

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find string literals manually or just replace common phrases
    # Let's replace the common english words we know are used in headers and buttons.
    phrases = [
        "Welcome to Fresh Tg Store!",
        "Premium services:", "Buy accounts, sessions, and top up instantly.",
        "Refer & Earn:", "Invite friends and earn", "of their deposits!",
        "Developer:", "You must join our channels first!",
        "Join all required channels and then tap", "Verify Joined",
        "TERMS & CONDITIONS", "Please read and accept our Terms & Conditions before using the bot.",
        "USER PROFILE", "User ID:", "Balance:", "Deposited:", "Referred Users:", "Joined:",
        "Your Referral Link:", "Set a public bot username to enable referrals.",
        "Share this link with your friends to earn bonuses!",
        "My Statistics", "Accounts Bought:", "Referrals:", "Total Spent:", "Total Deposited:",
        "View Purchase Logs", "Referral Logs",
        "Purchase History", "Page", "No purchases found.", "Prev", "Back", "Next",
        "Add Funds", "Choose your preferred payment method below:",
        "Add Funds by UPI", "Cwallet (5% BONUS)",
        "Enter Deposit Amount (in", "Minimum deposit is", "Cancel",
        "Amount to Pay:", "Exchange Rate:", "Method:", "Address / ID:",
        "Send Proof:", "Please send the Transaction Hash (Link) or a Screenshot of the payment now.",
        "After paying, send a clear Screenshot here:", "Deposit request submitted! Please wait for admin approval.",
        "NEW DEPOSIT REQUEST", "User:", "Request:", "Ref:", "Accept", "Reject", "Custom Amount",
        "Select a Country:", "No stock available at the moment. Please check back later!",
        "Select Year & Price for", "No stock left for",
        "Confirm Purchase", "Country:", "Year:", "Price:", "Are you sure?",
        "Confirm Buy", "Processing your order...", "Please wait while we initialize the session.",
        "Order Active!", "Phone:", "INSTRUCTIONS:", "Open Telegram & Add Account",
        "Enter the number above.", "Please wait!", "The bot is actively listening for your OTP and will send it automatically once Telegram delivers it.",
        "Note: If no OTP is received within 10 minutes, the bot will auto-cancel and refund your balance automatically.",
        "Latest OTP Fetched!", "OTP:", "Finish & Logout", "Get OTP Again",
        "Order Expired!", "The 10-minute limit for", "ran out. Your money", "has been automatically refunded.",
        "ADVANCED ADMIN DASHBOARD", "Users:", "Available Stock:", "Pending Deposits:"
    ]
    
    for p in phrases:
        content = content.replace(p, translate_str(p))
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Font update complete.")
