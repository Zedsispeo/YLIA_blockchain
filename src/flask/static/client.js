const POLL_INTERVAL = 1500;

// Attache un listener uniquement si l'élément existe. La page client ne contient
// qu'une partie des contrôles du tableau de bord ; sans ce garde-fou, un
// getElementById(...) null faisait planter tout le script et désactivait de fait
// le bouton "Register Peer".
function on(id, event, handler){
  const el = document.getElementById(id);
  if (el) el.addEventListener(event, handler);
}

// Met à jour textContent d'un élément seulement s'il est présent.
function setText(id, value){
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

async function api(path, method='GET', body=null){
  const opts = { method, headers: {} };
  if (body){ opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const resp = await fetch(path, opts);
  return resp.json();
}

function renderBlocks(chain){
  const container = document.getElementById('blocks');
  container.innerHTML = '';
  chain.forEach(block =>{
    const el = document.createElement('div');
    el.className = 'block-card' + (block.is_consistent === false || block.is_valid_signature === false ? ' invalid' : '');
    const hashPreview = block.hash ? block.hash.slice(0,28) + '...' : '';
    const prevHash = block.previous_hash ? block.previous_hash.slice(0,28) + '...' : '';
    const validityLabels = [];
    if (block.is_consistent === false) validityLabels.push('HASH MISMATCH');
    if (block.is_valid_signature === false) validityLabels.push('BAD SIGNATURE');
    el.innerHTML = `
      <div class="block-head">
        <div>
          <strong>Block ${block.index}</strong>
          <div class="muted">${new Date(block.timestamp*1000).toLocaleString()}</div>
        </div>
        <div style="text-align:right">
          <div class="hash">${hashPreview}</div>
          ${validityLabels.length ? `<div style="color:#ffb3b3;font-weight:600">${validityLabels.join(' • ')}</div>` : ''}
        </div>
      </div>
      <div class="txlist"><strong>Transactions:</strong><pre>${JSON.stringify(block.transactions, null, 2)}</pre></div>
      <div class="muted">Validator: ${block.validator || '-'} — Prev: ${prevHash}</div>
    `;
    container.appendChild(el);
  });
}

function renderLogs(logs){
  const el = document.getElementById('logs');
  if(!el) return;
  if(!logs || logs.length===0){ el.textContent = '(no logs)'; return }
  el.innerHTML = logs.map(l=>`<div>• ${l.msg}</div>`).join('');
}

function setValid(valid){
  const v = document.getElementById('valid_status');
  if(!v) return;
  v.textContent = valid ? 'VALID' : 'INVALID';
  v.className = 'pill ' + (valid ? 'valid' : 'invalid');
}

// Solde du client : l'identité du nœud (issue de sa clé) donne l'adresse, dont
// on lit ensuite le solde confirmé. Le client est destinataire passif de credits.
async function refreshBalance(){
  try{
    const info = await api('/node');
    const address = info.address;
    setText('client_address', address || '—');
    if(!address) return;
    const bal = await api('/balance/' + encodeURIComponent(address));
    setText('token_balance', bal.balance ?? 0);
  }catch(e){ console.error(e); setText('token_balance', '—'); }
}

async function refresh(){
  try{
    await refreshBalance();
    const data = await api('/chain');
    renderBlocks(data.chain || []);
    // pending transactions endpoint
    const pending = await api('/pending');
    setText('pending_count', pending.count || 0);
    // validation endpoint
    const valid = await api('/validate');
    setValid(Boolean(valid.valid));
    // peers
    try{
      const nodes = await api('/nodes');
      const peers = nodes.peers || [];
      setText('peers_list', peers.length ? peers.join(', ') : '(none)');
    }catch(e){ setText('peers_list', '(error)'); }
    const logs = await api('/logs');
    renderLogs(logs.logs || []);
  }catch(e){ console.error(e) }
}

document.getElementById('refresh').addEventListener('click', refresh);

on('mine', 'click', async ()=>{
  try{
    const data = await api('/mine');
    await refresh();
    markStep('step_mine');
    alert(data.message || 'Mined');
  }catch(e){ console.error(e) }
});

on('addtx', 'click', async ()=>{
  const sender = document.getElementById('sender').value;
  const recipient = document.getElementById('recipient').value;
  const amount = Number(document.getElementById('amount').value);
  try{
    // use_root=true tells the server to sign the transaction for demo purposes
    const data = await api('/transactions/new','POST',{sender,recipient,amount, use_root: true});
    markStep('step_tx');
    await refresh();
    alert(data.message || 'Added');
  }catch(e){ console.error(e) }
});

on('tamper_submit', 'click', async ()=>{
  const idx = Number(document.getElementById('tamper_index').value);
  let tx;
  try{ tx = JSON.parse(document.getElementById('tamper_tx').value); }catch(e){ alert('Transaction JSON invalide'); return }
  try{
    const data = await api('/tamper','POST',{index:idx, transaction:tx});
    markStep('step_tamper');
    await refresh();
    alert(data.message || 'Tampered');
  }catch(e){ console.error(e) }
});

on('broadcast_tampered', 'click', async ()=>{
  const idx = Number(document.getElementById('tamper_index').value);
  if(!idx){ alert('Choisir un index de bloc à broadcast'); return }
  try{
    // get local chain and peers
    const chainResp = await api('/chain');
    const nodesResp = await api('/nodes');
    const peers = nodesResp.peers || [];
    if(peers.length===0){ alert('Aucun peer enregistré'); return }
    const block = (chainResp.chain || []).find(b => b.index === idx);
    if(!block){ alert('Bloc introuvable localement'); return }

    // post block to each peer's /blocks/propose
    const results = [];
    // prepare a safe copy of the block: ensure transactions have required keys
    function normalizeTx(tx){
      // tx may be a plain object or already include fields
      const now = Date.now()/1000;
      return {
        type: tx.type || tx['type'] || 'credit',
        sender: tx.sender || tx['sender'] || 'attacker',
        recipient: tx.recipient || tx['recipient'] || 'pizzha.se',
        amount: ('amount' in tx) ? tx.amount || tx['amount'] || 0 : 0,
        public_key: tx.public_key || tx['public_key'] || '',
        timestamp: tx.timestamp || tx['timestamp'] || now,
        nonce: tx.nonce || tx['nonce'] || '',
        signature: ('signature' in tx) ? tx.signature || tx['signature'] : null,
      };
    }

    const blockToSend = JSON.parse(JSON.stringify(block));
    if(Array.isArray(blockToSend.transactions)){
      blockToSend.transactions = blockToSend.transactions.map(t => normalizeTx(t));
    }

    for(const p of peers){
      try{
        const url = p.replace(/\/$/, '') + '/blocks/receive';
        // /blocks/receive expects the block dict as the top-level JSON body
        const resp = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(blockToSend)});
        const json = await resp.json().catch(()=>({}));
        results.push({peer:p, status: resp.status, body: json});
      }catch(err){
        results.push({peer:p, error: String(err)});
      }
    }

    // show results in alerts and logs
    const ok = results.filter(r => r.status && (r.status===201 || r.status===200));
    const nok = results.filter(r => !r.status || (r.status && r.status>=400));
    await refresh();
    // show detailed results
    const lines = results.map(r => {
      if(r.error) return `${r.peer}: ERROR ${r.error}`;
      if(r.status===201 || r.status===200) return `${r.peer}: ACCEPTED`;
      const reason = r.body && r.body.reason ? r.body.reason : JSON.stringify(r.body || {})
      return `${r.peer}: REJECTED (${r.status}) - ${reason}`;
    });
    const msg = `Broadcast results:\n` + lines.join('\n');
    // Append to server logs for visibility to all users
    try{ await api('/logs','POST',{msg}); }catch(e){ console.warn('failed to append logs', e); }
    alert(`Broadcast done.\n` + lines.join('\n'));
    console.log('broadcast results', results);
  }catch(e){ console.error(e); alert('Erreur lors du broadcast') }
});

on('resolve', 'click', async ()=>{
  try{
    const data = await api('/nodes/resolve');
    markStep('step_resolve');
    await refresh();
    alert(data.message || 'Resolved');
  }catch(e){ console.error(e) }
});

on('reset_demo', 'click', async ()=>{
  if(!confirm('Reset demo to genesis state? This will clear the chain and logs.')) return;
  try{
    const data = await api('/reset','POST',{});
    markStep('step_reset');
    await refresh();
    alert(data.message || 'Reset');
  }catch(e){ console.error(e) }
});

on('add_peer', 'click', async ()=>{
  const addr = document.getElementById('peer_addr').value.trim();
  if(!addr){ alert('Entrez l\'URL du pair, ex: http://node_a:5000'); return }
  try{
    const data = await api('/nodes/register','POST',{nodes:[addr]});
    await refresh();
    alert(data.message || 'Peer registered');
  }catch(e){ console.error(e); alert('Erreur registering peer') }
});

function markStep(id){
  document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));
  const el = document.getElementById(id);
  if(el) el.classList.add('active');
}

// poll periodically
setInterval(refresh, POLL_INTERVAL);
// initial
refresh();
