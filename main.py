import os
import logging
import time
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import configparser
import traceback
from bot import PumpBot
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "pump_fun_bot_secret")

# Initialize bot instance
bot = None

@app.route('/')
def index():
    """Main page for the Pump.fun bot interface"""
    config = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        config.read('config.ini')
    else:
        # Default configuration
        config['SETTINGS'] = {
            'rpc_url': 'https://api.mainnet-beta.solana.com',
            'slippage': '10',
            'buy_delay': '2',
        }
        config['WALLETS'] = {}
        config['BUY_AMOUNTS'] = {
            'amount1': '0.01',
            'amount2': '0.05',
            'amount3': '0.001',
            'amount4': '0.1'
        }
        config['SELL_CONDITIONS'] = {
            'profit_percentage': '50',
            'timeout_seconds': '300',
            'num_buyers': '10'
        }
        
        with open('config.ini', 'w') as f:
            config.write(f)
    
    return render_template('index.html', config=config)

@app.route('/save_config', methods=['POST'])
def save_config():
    """Save bot configuration"""
    try:
        config = configparser.ConfigParser()
        
        # Settings section
        config['SETTINGS'] = {
            'rpc_url': request.form.get('rpc_url'),
            'slippage': request.form.get('slippage'),
            'buy_delay': request.form.get('buy_delay'),
        }
        
        # Wallets section
        config['WALLETS'] = {}
        for i in range(1, 5):  # Support up to 4 wallets
            wallet_key = request.form.get(f'wallet_key_{i}')
            if wallet_key and wallet_key.strip():
                config['WALLETS'][f'wallet_{i}'] = wallet_key.strip()
        
        # Buy amounts
        config['BUY_AMOUNTS'] = {
            'amount1': request.form.get('amount1', '0.01'),
            'amount2': request.form.get('amount2', '0.05'),
            'amount3': request.form.get('amount3', '0.001'),
            'amount4': request.form.get('amount4', '0.1')
        }
        
        # Sell conditions
        config['SELL_CONDITIONS'] = {
            'profit_percentage': request.form.get('profit_percentage', '50'),
            'timeout_seconds': request.form.get('timeout_seconds', '300'),
            'num_buyers': request.form.get('num_buyers', '10')
        }
        
        with open('config.ini', 'w') as f:
            config.write(f)
            
        flash('Configuration saved successfully!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Error saving configuration: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/start_bot', methods=['POST'])
def start_bot():
    """Start the Pump.fun sniper bot"""
    global bot
    try:
        token_address = request.form.get('token_address')
        if not token_address or not token_address.strip():
            flash('Token address is required!', 'warning')
            return redirect(url_for('index'))
            
        # Create bot instance if it doesn't exist
        if bot is None:
            bot = PumpBot()
            
        # Start bot with the specified token
        success, message = bot.start(token_address.strip())
        
        if success:
            flash(f'Bot started successfully! {message}', 'success')
        else:
            flash(f'Failed to start bot: {message}', 'danger')
            
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Error starting bot: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    """Stop the Pump.fun sniper bot"""
    global bot
    try:
        if bot:
            bot.stop()
            flash('Bot stopped successfully!', 'success')
        else:
            flash('Bot is not running!', 'warning')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Error stopping bot: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/bot_status', methods=['GET'])
def bot_status():
    """Get current bot status"""
    global bot
    try:
        if bot:
            status = bot.get_status()
        else:
            status = {
                'running': False,
                'token': None,
                'wallets': 0,
                'transactions': []
            }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting bot status: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
        
@app.route('/test_bot', methods=['POST'])
def test_bot():
    """Test the bot with fake tokens and simulated transactions"""
    global bot
    try:
        # Get test parameters
        token_address = request.form.get('token_address', 'TEST' + str(int(time.time())))
        test_mode = request.form.get('test_mode', 'buy_sell')  # 'buy', 'sell', or 'buy_sell'
        
        # Create bot instance if it doesn't exist
        if bot is None:
            bot = PumpBot()
            
        # Configure the bot for testing
        bot.test_mode = True
        
        # Start bot with the specified token
        success, message = bot.start(token_address)
        
        if not success:
            flash(f'Failed to start test bot: {message}', 'danger')
            return redirect(url_for('index'))
            
        # Add some fake transactions for testing
        from wallet import Wallet, PublicKey
        from solana_client import SolanaClient
        
        # Create a test client and wallet
        test_client = SolanaClient()
        test_wallet = Wallet("test_private_key", test_client)
        
        # Simulate a buy transaction
        if test_mode in ['buy', 'buy_sell']:
            bot.add_transaction(0, 'buy', 0.05, 10.5, 'test-tx-buy-' + str(int(time.time())))
            flash('Simulated buy transaction added', 'success')
            
        # Simulate a sell transaction
        if test_mode in ['sell', 'buy_sell']:
            bot.add_transaction(0, 'sell', 0.06, 10.5, 'test-tx-sell-' + str(int(time.time())))
            flash('Simulated sell transaction added', 'success')
        
        # If buy_sell mode, simulate profit
        if test_mode == 'buy_sell':
            flash('Test completed with simulated 20% profit', 'success')
        
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error in test mode: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Error testing bot: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/test_wallet', methods=['POST'])
def test_wallet():
    """Test connection to a specific wallet"""
    try:
        data = request.get_json()
        wallet_key = data.get('wallet_key')
        
        if not wallet_key or not wallet_key.strip():
            return jsonify({'success': False, 'message': 'Wallet key is required'})
            
        from wallet import Wallet
        from solana_client import SolanaClient
        
        solana_client = SolanaClient("https://api.mainnet-beta.solana.com")
        wallet = Wallet(wallet_key, solana_client)
        
        # Test wallet connection
        balance = wallet.get_balance()
        
        return jsonify({
            'success': True, 
            'message': f'Wallet connected successfully! Balance: {balance} SOL'
        })
    except Exception as e:
        logger.error(f"Error testing wallet: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
