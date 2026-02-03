from eth_account import Account
try:
    key = "0xa31f000a223c023c542060055b5abc05ca1c110a3c5255863316650c70448512"
    print(Account.from_key(key).address)
except Exception as e:
    print(e)
