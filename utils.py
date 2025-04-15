import logging
import json
import base58
from decimal import Decimal, getcontext

# Set decimal precision
getcontext().prec = 10

logger = logging.getLogger(__name__)

def calculate_profit_percentage(buy_price, current_price):
    """
    Calculate profit percentage
    
    Args:
        buy_price (float): Buy price
        current_price (float): Current price
        
    Returns:
        float: Profit percentage
    """
    if buy_price == 0:
        return 0
        
    try:
        buy_price_decimal = Decimal(str(buy_price))
        current_price_decimal = Decimal(str(current_price))
        
        profit_decimal = ((current_price_decimal - buy_price_decimal) / buy_price_decimal) * Decimal('100')
        return float(profit_decimal)
    except Exception as e:
        logger.error(f"Error calculating profit percentage: {str(e)}")
        return 0

def format_sol_amount(amount):
    """
    Format SOL amount with proper precision
    
    Args:
        amount (float): SOL amount
        
    Returns:
        str: Formatted SOL amount
    """
    try:
        if amount < 0.001:
            return f"{amount:.9f}"
        elif amount < 0.01:
            return f"{amount:.6f}"
        elif amount < 1:
            return f"{amount:.4f}"
        else:
            return f"{amount:.2f}"
    except Exception as e:
        logger.error(f"Error formatting SOL amount: {str(e)}")
        return str(amount)

def shorten_address(address, chars=4):
    """
    Shorten an address for display
    
    Args:
        address (str): Address to shorten
        chars (int): Number of characters to keep at start and end
        
    Returns:
        str: Shortened address
    """
    if not address:
        return ""
        
    if len(address) <= chars * 2:
        return address
        
    return f"{address[:chars]}...{address[-chars:]}"

def format_timestamp(timestamp, format_str="%Y-%m-%d %H:%M:%S"):
    """
    Format a timestamp
    
    Args:
        timestamp (int): Unix timestamp
        format_str (str): Format string
        
    Returns:
        str: Formatted timestamp
    """
    from datetime import datetime
    
    try:
        return datetime.fromtimestamp(timestamp).strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting timestamp: {str(e)}")
        return str(timestamp)

def validate_solana_address(address):
    """
    Validate a Solana address
    
    Args:
        address (str): Address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        if not address or len(address) < 32 or len(address) > 44:
            return False
            
        # Try to decode base58
        try:
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        except Exception:
            return False
    except Exception as e:
        logger.error(f"Error validating Solana address: {str(e)}")
        return False

def encode_base58(data):
    """
    Encode bytes as base58
    
    Args:
        data (bytes): Data to encode
        
    Returns:
        str: Base58 encoded string
    """
    try:
        return base58.b58encode(data).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding base58: {str(e)}")
        return None

def decode_base58(encoded):
    """
    Decode base58 string to bytes
    
    Args:
        encoded (str): Base58 encoded string
        
    Returns:
        bytes: Decoded bytes
    """
    try:
        return base58.b58decode(encoded)
    except Exception as e:
        logger.error(f"Error decoding base58: {str(e)}")
        return None
