// Main JavaScript functionality for Pump.fun Sniper Bot

// Prevent form resubmission on page refresh
if (window.history.replaceState) {
    window.history.replaceState(null, null, window.location.href);
}

// Format SOL amount with proper precision
function formatSolAmount(amount) {
    if (amount < 0.001) {
        return amount.toFixed(9);
    } else if (amount < 0.01) {
        return amount.toFixed(6);
    } else if (amount < 1) {
        return amount.toFixed(4);
    } else {
        return amount.toFixed(2);
    }
}

// Shorten wallet address for display
function shortenAddress(address, chars = 4) {
    if (!address) return '';
    if (address.length <= chars * 2) return address;
    return `${address.substring(0, chars)}...${address.substring(address.length - chars)}`;
}

// Copy text to clipboard
function copyToClipboard(text) {
    const tempInput = document.createElement('input');
    tempInput.style.position = 'absolute';
    tempInput.style.left = '-9999px';
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand('copy');
    document.body.removeChild(tempInput);
    
    // Show a tooltip or notification
    alert('Copied to clipboard: ' + text);
}

// Validate Solana address format
function isValidSolanaAddress(address) {
    // Basic validation: length and characters
    return /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(address);
}

// Update bot status UI
function updateBotStatus() {
    fetch('/bot_status')
        .then(response => response.json())
        .then(data => {
            // Update status indicators
            const statusElement = document.getElementById('statusValue');
            if (data.running) {
                statusElement.textContent = 'Running';
                statusElement.className = 'badge bg-success';
                
                // Enable stop button, disable start button
                document.getElementById('stopBtn').disabled = false;
                document.getElementById('startBtn').disabled = true;
            } else {
                statusElement.textContent = 'Stopped';
                statusElement.className = 'badge bg-secondary';
                
                // Enable start button, disable stop button
                document.getElementById('stopBtn').disabled = true;
                document.getElementById('startBtn').disabled = false;
            }
            
            // Update token info
            const tokenElement = document.getElementById('tokenValue');
            if (data.token) {
                tokenElement.textContent = shortenAddress(data.token);
                tokenElement.setAttribute('title', data.token);
                tokenElement.classList.add('text-truncate');
            } else {
                tokenElement.textContent = 'N/A';
                tokenElement.removeAttribute('title');
            }
            
            // Update wallet count
            document.getElementById('walletsValue').textContent = data.wallets;
            
            // Update transaction count and list
            const txCount = data.transactions ? data.transactions.length : 0;
            document.getElementById('transactionsValue').textContent = txCount;
            
            // Update transaction list if there are transactions
            const txListElement = document.getElementById('transactionsList');
            if (txCount > 0) {
                let txHtml = '';
                
                // Sort transactions by timestamp (newest first)
                const sortedTx = [...data.transactions].reverse();
                
                sortedTx.forEach(tx => {
                    let txClass = '';
                    if (tx.type.includes('BUY')) {
                        txClass = tx.type.includes('FAILED') ? 'table-danger' : 'table-info';
                    } else if (tx.type.includes('SELL')) {
                        txClass = tx.type.includes('FAILED') ? 'table-danger' : 'table-success';
                    } else if (tx.type.includes('ERROR')) {
                        txClass = 'table-warning';
                    }
                    
                    txHtml += `<tr class="${txClass}">
                        <td>${tx.timestamp}</td>
                        <td>${tx.wallet}</td>
                        <td>${tx.type}</td>
                        <td>${tx.amount} SOL</td>
                        <td>${tx.token_amount || 'N/A'}</td>
                        <td>${tx.tx_hash ? `<a href="#" onclick="copyToClipboard('${tx.tx_hash}'); return false;" title="Copy TX hash">
                            ${shortenAddress(tx.tx_hash, 4)}</a>` : 'N/A'}</td>
                    </tr>`;
                });
                
                txListElement.innerHTML = txHtml;
            } else {
                txListElement.innerHTML = '<tr><td colspan="6" class="text-center">No transactions yet</td></tr>';
            }
        })
        .catch(error => console.error('Error fetching bot status:', error));
}

// Handle form validation
document.addEventListener('DOMContentLoaded', function() {
    // Validate token address on bot start form
    const botControlForm = document.getElementById('botControlForm');
    if (botControlForm) {
        botControlForm.addEventListener('submit', function(e) {
            const tokenAddress = document.getElementById('token_address').value;
            if (!isValidSolanaAddress(tokenAddress)) {
                e.preventDefault();
                alert('Please enter a valid Solana token address');
            }
        });
    }
    
    // Setup stop button action
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            fetch('/stop_bot', { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                }
            })
            .catch(error => console.error('Error stopping bot:', error));
        });
    }
    
    // Validate test token address (if provided)
    const testBotForm = document.getElementById('testBotForm');
    if (testBotForm) {
        testBotForm.addEventListener('submit', function(e) {
            const tokenAddress = document.getElementById('test_token_address').value;
            if (tokenAddress && !isValidSolanaAddress(tokenAddress)) {
                e.preventDefault();
                alert('Please enter a valid Solana token address or leave empty for auto-generation');
            }
        });
    }
    
    // Setup wallet test functionality
    const testWalletButtons = document.querySelectorAll('.test-wallet');
    testWalletButtons.forEach(button => {
        button.addEventListener('click', function() {
            const walletId = this.getAttribute('data-wallet-id');
            const walletKey = document.getElementById(`wallet_key_${walletId}`).value;
            const statusElement = document.querySelector(`.wallet-status-${walletId}`);
            
            if (!walletKey) {
                statusElement.innerHTML = '<span class="text-warning">Please enter a wallet key</span>';
                return;
            }
            
            statusElement.innerHTML = '<span class="text-info">Testing wallet connection...</span>';
            
            fetch('/test_wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ wallet_key: walletKey })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusElement.innerHTML = `<span class="text-success">${data.message}</span>`;
                } else {
                    statusElement.innerHTML = `<span class="text-danger">${data.message}</span>`;
                }
            })
            .catch(error => {
                console.error('Error testing wallet:', error);
                statusElement.innerHTML = '<span class="text-danger">Error testing wallet connection</span>';
            });
        });
    });
    
    // Initialize tooltips (if any)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Toggle password visibility
    const toggleButtons = document.querySelectorAll('.toggle-password');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const targetInput = document.querySelector(targetId);
            const icon = this.querySelector('i');
            
            if (targetInput.type === 'password') {
                targetInput.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                targetInput.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });
    
    // Poll for bot status updates
    updateBotStatus();
    setInterval(updateBotStatus, 5000); // Update every 5 seconds
});
