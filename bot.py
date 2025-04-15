import os
import time
import threading
import logging
import configparser
from datetime import datetime
from wallet import Wallet
from solana_client import SolanaClient
from pump_api import PumpFunAPI
from utils import calculate_profit_percentage

logger = logging.getLogger(__name__)

class PumpBot:
    def __init__(self):
        """Initialize Pump.fun sniper bot"""
        self.running = False
        self.token_address = None
        self.wallets = []
        self.solana_client = None
        self.pump_api = None
        self.config = None
        self.thread = None
        self.transactions = []
        self.lock = threading.Lock()
        self.test_mode = False  # Flag for test mode
    
    def load_config(self):
        """Load configuration from config.ini"""
        config = configparser.ConfigParser()
        if not os.path.exists('config.ini'):
            raise Exception("Config file not found! Please configure the bot first.")
        
        config.read('config.ini')
        self.config = config
        
        # Initialize Solana client
        rpc_url = config.get('SETTINGS', 'rpc_url', fallback='https://api.mainnet-beta.solana.com')
        self.solana_client = SolanaClient(rpc_url)
        
        # Initialize Pump.fun API
        self.pump_api = PumpFunAPI(self.solana_client)
        
        # Load wallets
        self.wallets = []
        for key, value in config['WALLETS'].items():
            if key.startswith('wallet_') and value.strip():
                wallet = Wallet(value.strip(), self.solana_client)
                self.wallets.append(wallet)
                
        if not self.wallets:
            raise Exception("No wallets configured! Please add at least one wallet.")
            
        logger.info(f"Loaded {len(self.wallets)} wallet(s)")
        
        return True
        
    def start(self, token_address):
        """Start the sniper bot with the specified token"""
        if self.running:
            return False, "Bot is already running"
            
        try:
            # Load configuration
            self.load_config()
            
            self.token_address = token_address
            self.running = True
            self.transactions = []
            
            # Start bot in a separate thread
            self.thread = threading.Thread(target=self._run)
            self.thread.daemon = True
            self.thread.start()
            
            logger.info(f"Bot started for token: {token_address}")
            return True, f"Monitoring token {token_address} with {len(self.wallets)} wallet(s)"
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            self.running = False
            return False, str(e)
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info("Bot stopped")
        
    def get_status(self):
        """Get current bot status"""
        with self.lock:
            return {
                'running': self.running,
                'token': self.token_address,
                'wallets': len(self.wallets) if self.wallets else 0,
                'transactions': self.transactions
            }
            
    def add_transaction(self, wallet_idx, tx_type, amount, token_amount=None, tx_hash=None):
        """Add a transaction to the history"""
        with self.lock:
            tx = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'wallet': f"Wallet {wallet_idx+1}",
                'type': tx_type,
                'amount': amount,
                'token_amount': token_amount,
                'tx_hash': tx_hash
            }
            self.transactions.append(tx)
            # Keep only the latest 100 transactions
            if len(self.transactions) > 100:
                self.transactions = self.transactions[-100:]
    
    def _run(self):
        """Main bot loop"""
        try:
            logger.info(f"Bot running for token: {self.token_address}")
            
            # Get configuration values
            slippage = self.config.getfloat('SETTINGS', 'slippage', fallback=10.0)
            buy_delay = self.config.getfloat('SETTINGS', 'buy_delay', fallback=2.0)
            
            # Buy amounts for each wallet
            buy_amounts = []
            for i in range(1, 5):
                amount_key = f'amount{i}'
                if amount_key in self.config['BUY_AMOUNTS']:
                    buy_amounts.append(self.config.getfloat('BUY_AMOUNTS', amount_key))
            
            # Ensure we have enough buy amounts for all wallets
            while len(buy_amounts) < len(self.wallets):
                buy_amounts.append(0.01)  # Default amount
                
            # Check if token exists on Pump.fun
            token_info = self.pump_api.get_token_info(self.token_address)
            
            if not token_info:
                logger.info(f"Token {self.token_address} not yet available on Pump.fun. Waiting for launch...")
                
            # Buy tokens for each wallet
            buy_results = {}
            for wallet_idx, wallet in enumerate(self.wallets):
                if not self.running:
                    break
                    
                buy_amount = buy_amounts[wallet_idx]
                
                # Skip wallets with 0 buy amount
                if buy_amount <= 0:
                    continue
                    
                # Check wallet balance
                balance = wallet.get_balance()
                if balance < buy_amount:
                    logger.warning(f"Wallet {wallet_idx+1} has insufficient balance: {balance} SOL, need {buy_amount} SOL")
                    self.add_transaction(wallet_idx, "ERROR", buy_amount, 
                                        tx_hash=None, 
                                        token_amount=f"Insufficient balance: {balance} SOL")
                    continue
                
                logger.info(f"Buying with wallet {wallet_idx+1}, amount: {buy_amount} SOL")
                
                # Add buy delay
                if buy_delay > 0 and wallet_idx > 0:
                    time.sleep(buy_delay)
                    
                # Buy token
                success, tx_info = self.pump_api.buy_token(self.token_address, wallet, buy_amount, slippage)
                
                if success:
                    logger.info(f"Buy successful for wallet {wallet_idx+1}: {tx_info}")
                    buy_results[wallet_idx] = tx_info
                    self.add_transaction(wallet_idx, "BUY", buy_amount, 
                                        tx_hash=tx_info.get('transaction_hash'), 
                                        token_amount=tx_info.get('token_amount'))
                else:
                    logger.error(f"Buy failed for wallet {wallet_idx+1}: {tx_info}")
                    self.add_transaction(wallet_idx, "BUY FAILED", buy_amount, 
                                        tx_hash=None, 
                                        token_amount=f"Error: {tx_info}")
            
            # If no buys were successful, exit
            if not buy_results:
                logger.warning("No successful buys, stopping bot")
                self.running = False
                return
                
            # Monitor and execute auto-sell
            self._monitor_and_sell(buy_results)
                
        except Exception as e:
            logger.error(f"Error in bot thread: {str(e)}")
        finally:
            self.running = False
            logger.info("Bot thread stopped")
            
    def _monitor_and_sell(self, buy_results):
        """Monitor token price and sell based on conditions"""
        
        # Get sell conditions from config
        profit_threshold = self.config.getfloat('SELL_CONDITIONS', 'profit_percentage', fallback=50.0)
        timeout_seconds = self.config.getfloat('SELL_CONDITIONS', 'timeout_seconds', fallback=300.0)
        min_buyers = self.config.getint('SELL_CONDITIONS', 'num_buyers', fallback=10)
        
        logger.info(f"Monitoring for sell conditions: profit >= {profit_threshold}%, timeout: {timeout_seconds}s, buyers: {min_buyers}")
        
        # Start time for timeout calculation
        start_time = time.time()
        
        slippage = self.config.getfloat('SETTINGS', 'slippage', fallback=10.0)
        
        while self.running and time.time() - start_time < timeout_seconds:
            try:
                # Get current token info
                token_info = self.pump_api.get_token_info(self.token_address)
                
                if not token_info:
                    logger.warning("Could not get token info, retrying...")
                    time.sleep(5)
                    continue
                
                current_price = token_info.get('price', 0)
                buyers_count = token_info.get('buyers_count', 0)
                
                # Check sell conditions for each wallet that bought successfully
                for wallet_idx, buy_info in buy_results.items():
                    # Skip already sold positions
                    if buy_info.get('sold', False):
                        continue
                        
                    buy_price = buy_info.get('price', 0)
                    profit_percentage = calculate_profit_percentage(buy_price, current_price)
                    
                    # Check if sell conditions are met
                    sell_reason = None
                    if profit_percentage >= profit_threshold:
                        sell_reason = f"Profit target reached: {profit_percentage:.2f}%"
                    elif buyers_count >= min_buyers:
                        sell_reason = f"Buyer count target reached: {buyers_count} buyers"
                    elif time.time() - start_time >= timeout_seconds:
                        sell_reason = f"Timeout reached: {int(time.time() - start_time)}s"
                        
                    if sell_reason:
                        logger.info(f"Selling token for wallet {wallet_idx+1}: {sell_reason}")
                        
                        wallet = self.wallets[wallet_idx]
                        token_balance = buy_info.get('token_amount', 0)
                        
                        # Sell token
                        success, tx_info = self.pump_api.sell_token(self.token_address, wallet, token_balance, slippage)
                        
                        if success:
                            logger.info(f"Sell successful for wallet {wallet_idx+1}: {tx_info}")
                            self.add_transaction(wallet_idx, "SELL", tx_info.get('amount_sol', 0), 
                                                tx_hash=tx_info.get('transaction_hash'), 
                                                token_amount=token_balance)
                            buy_info['sold'] = True
                        else:
                            logger.error(f"Sell failed for wallet {wallet_idx+1}: {tx_info}")
                            self.add_transaction(wallet_idx, "SELL FAILED", 0, 
                                                tx_hash=None, 
                                                token_amount=f"Error: {tx_info}")
                
                # Check if all positions are sold
                all_sold = all(buy_info.get('sold', False) for buy_info in buy_results.values())
                if all_sold:
                    logger.info("All positions sold, stopping bot")
                    self.running = False
                    break
                    
                # Sleep to avoid hammering the API
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in monitoring thread: {str(e)}")
                time.sleep(5)
                
        # Force sell any remaining positions at timeout
        if self.running:
            logger.info("Timeout reached, selling remaining positions")
            
            for wallet_idx, buy_info in buy_results.items():
                if buy_info.get('sold', False):
                    continue
                    
                wallet = self.wallets[wallet_idx]
                token_balance = buy_info.get('token_amount', 0)
                
                logger.info(f"Selling remaining token for wallet {wallet_idx+1} (timeout)")
                
                # Sell token
                success, tx_info = self.pump_api.sell_token(self.token_address, wallet, token_balance, slippage)
                
                if success:
                    logger.info(f"Timeout sell successful for wallet {wallet_idx+1}: {tx_info}")
                    self.add_transaction(wallet_idx, "SELL (TIMEOUT)", tx_info.get('amount_sol', 0), 
                                        tx_hash=tx_info.get('transaction_hash'), 
                                        token_amount=token_balance)
                else:
                    logger.error(f"Timeout sell failed for wallet {wallet_idx+1}: {tx_info}")
                    self.add_transaction(wallet_idx, "SELL FAILED (TIMEOUT)", 0, 
                                        tx_hash=None, 
                                        token_amount=f"Error: {tx_info}")
            
            self.running = False
