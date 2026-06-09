const POLL_INTERVAL = 10000;

// Roles we will create for the demo
const DEMO_ROLES = [
  {key: 'customer1', label: 'Customer 1'},
  {key: 'customer2', label: 'Customer 2'},
  {key: 'responsable', label: 'Responsable'},
];

function storageKeyForRole(roleKey){ return `ylia_demo_identity_${roleKey}` }

async function ensureDemoIdentities(){
  const identities = {};
  for(const r of DEMO_ROLES){
    const k = storageKeyForRole(r.key);
    let stored = localStorage.getItem(k);
    if(stored){
      try{ identities[r.key] = JSON.parse(stored); continue }catch(e){}
    }
    // create a wallet on the server and store it
    try{
      const w = await api('/wallet/new');
      const obj = {role:r.key, label:r.label, address:w.address, private_key:w.private_key, public_key:w.public_key};
      localStorage.setItem(k, JSON.stringify(obj));
      identities[r.key] = obj;
    }catch(e){
      console.error('failed to create wallet', e);
    }
  }
  return identities;
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
  if(!logs || logs.length===0){ el.textContent = '(no logs)'; return }
  el.innerHTML = logs.map(l=>`<div>• ${l.msg}</div>`).join('');
}

function setValid(valid){
  const v = document.getElementById('valid_status');
  v.textContent = valid ? 'VALID' : 'INVALID';
  v.className = 'pill ' + (valid ? 'valid' : 'invalid');
}

async function refresh(){
  try{
    const data = await api('/chain');
    renderBlocks(data.chain || []);
    // pending transactions endpoint
    const pending = await api('/pending');
    document.getElementById('pending_count').textContent = pending.count || 0;
    // validation endpoint
    const valid = await api('/validate');
    setValid(Boolean(valid.valid));
    // peers
    try{
      const nodes = await api('/nodes');
      const peers = nodes.peers || [];
      document.getElementById('peers_list').textContent = peers.length ? peers.join(', ') : '(none)';
    }catch(e){ document.getElementById('peers_list').textContent = '(error)'; }
    const logs = await api('/logs');
    renderLogs(logs.logs || []);

    // ensure demo identities exist and update UI selects + balances
    const ids = await ensureDemoIdentities();
    populateIdentitySelect(ids);
    populateRecipientSelect(ids);
    await renderBalances(ids);

  }catch(e){ console.error(e) }
}


// Show role picker overlay populated with demo identities.
async function showRolePicker(visible=true){
  // ensure overlay visible while we populate
  const overlay = document.getElementById('role_picker');
  if(overlay) overlay.style.display = visible ? 'flex' : 'none';
  const ids = await ensureDemoIdentities();
  const container = document.getElementById('role_buttons');
  if(!container) return;
  container.innerHTML = '';
  // Always show the three role badges; addresses may be generated lazily on click.
  DEMO_ROLES.forEach(r => {
    const addr = ids[r.key] ? ids[r.key].address : null;
    const btn = document.createElement('button');
    btn.className = 'btn warn';
    btn.style.minWidth = '160px';
    btn.textContent = addr ? `${r.label}\n${addr.slice(0,12)}...` : `${r.label}\n(créer)`;
    btn.onclick = async () => {
      // ensure identities exist (create if missing), then set selection
      const newIds = await ensureDemoIdentities();
      if(!newIds[r.key]){
        // fallback: show error and abort
        alert('Impossible de créer l\'identité, regardez la console pour les erreurs');
        return;
      }
      setCurrentIdentity(newIds, r.key);
      document.getElementById('role_picker').style.display = 'none';
      // start periodic refresh once chosen
      refresh();
      pollingStarted = true;
      if(!pollingTimer){ pollingTimer = setInterval(refresh, POLL_INTERVAL); }
    };
    container.appendChild(btn);
  });
}

function showRolePickerOverlay(){
  const el = document.getElementById('role_picker');
  if(el) el.style.display = 'flex';
}

// allow reopening the picker via header (we add a small handler below to create the button)
function addChangeRoleButton(){
  const header = document.querySelector('.topbar');
  if(!header) return;
  let btn = document.getElementById('change_role_btn');
  if(btn) return;
  btn = document.createElement('button');
  btn.id = 'change_role_btn';
  btn.className = 'btn';
  btn.style.marginLeft = '12px';
  btn.textContent = 'Changer de rôle';
  btn.onclick = ()=> {showRolePickerOverlay()};
  header.appendChild(btn);
}

// polling helpers
let pollingTimer = null;
let pollingStarted = false;
// current selection
let currentRoleKey = null;
let currentIdentity = null;

function setCurrentIdentity(ids, roleKey){
  const obj = ids[roleKey];
  if(!obj) return;
  currentRoleKey = roleKey;
  currentIdentity = obj;
  // update connected-as display
  const conn = document.getElementById('connected_as');
  if(conn) conn.textContent = `Connecté en tant que: ${obj.label} — ${obj.address}`;
  // update permissions
  updatePermissions(roleKey, obj);
  // keep hidden select in sync (if present)
  const sel = document.getElementById('identity_select');
  if(sel) sel.value = roleKey;
  // persist choice
  try{ localStorage.setItem('ylia_demo_current_role', roleKey); }catch(e){}
  // ensure role picker overlay is hidden once identity is set
  const picker = document.getElementById('role_picker');
  if(picker) picker.style.display = 'none';
}

function populateIdentitySelect(ids){
  const sel = document.getElementById('identity_select');
  if(!sel) return;
  const prev = sel.value;
  sel.innerHTML = '';
  DEMO_ROLES.forEach(r => {
    const obj = ids[r.key];
    if(!obj) return;
    const opt = document.createElement('option');
    opt.value = r.key;
    opt.textContent = `${r.label} — ${obj.address.slice(0,12)}...`;
    sel.appendChild(opt);
  });
  sel.value = prev || DEMO_ROLES[0].key;
  // set sender field
  setSenderFromIdentity(ids, sel.value);
  sel.onchange = ()=> setSenderFromIdentity(ids, sel.value);
}

function setSenderFromIdentity(ids, roleKey){
  const obj = ids[roleKey];
  if(!obj) return;
  // update UI permissions/role badge
  updatePermissions(roleKey, obj);
}

function updatePermissions(roleKey){
  const addBtn = document.getElementById('addtx');
  const recipient = document.getElementById('recipient');
  const amount = document.getElementById('amount');
  const badge = document.getElementById('role_badge');
  if(!addBtn || !recipient || !amount) return;
  const isResponsable = roleKey === 'responsable';
  if (badge){
    if(isResponsable){
    badge.textContent = 'Responsable — peut émettre des transactions';
    badge.className = 'role-badge';
    } else{
      badge.textContent = 'Customer — lecture seule';
      badge.className = 'role-badge muted';
    }
  }
  
}

function populateRecipientSelect(ids){
  const sel = document.getElementById('recipient');
  if(!sel) return;
  sel.innerHTML = '';
  DEMO_ROLES.forEach(r => {
    const obj = ids[r.key];
    if(!obj) return;
    const opt = document.createElement('option');
    opt.value = obj.address;
    opt.textContent = `${r.label} — ${obj.address.slice(0,12)}...`;
    sel.appendChild(opt);
  });
}

async function renderBalances(ids){
  try{
    const resp = await api('/balances');
    const balances = resp.balances || {};
    // create a small table under the status panel (or update if exists)
    let tbl = document.getElementById('balances_table');
    if(!tbl){
      const container = document.createElement('div');
      container.id = 'balances_table_container';
      container.innerHTML = '<h3>Soldes</h3><table id="balances_table"><thead><tr><th>Identité</th><th>Adresse</th><th>Soldes</th></tr></thead><tbody></tbody></table>';
      const statusCard = document.querySelector('.status');
      if(statusCard) statusCard.appendChild(container);
      tbl = document.getElementById('balances_table');
    }
    const tbody = tbl.querySelector('tbody');
    tbody.innerHTML = '';
    DEMO_ROLES.forEach(r => {
      const obj = ids[r.key];
      if(!obj) return;
      const row = document.createElement('tr');
      const bal = balances[obj.address] || 0;
      row.innerHTML = `<td>${r.label}</td><td class="hash">${obj.address}</td><td>${bal}</td>`;
      tbody.appendChild(row);
    });
  }catch(e){ console.warn('failed to load balances', e); }
}

document.getElementById('refresh').addEventListener('click', refresh);

document.getElementById('mine').addEventListener('click', async ()=>{
  try{
    const data = await api('/mine');
    await refresh();
    markStep('step_mine');
    alert(data.message || 'Mined');
  }catch(e){ console.error(e) }
});

document.getElementById('addtx').addEventListener('click', async ()=>{
  if(!currentIdentity){ alert('Choisissez d\'abord un rôle'); return }
  const stored = currentIdentity;
  const recipient = document.getElementById('recipient').value;
  const amount = Number(document.getElementById('amount').value);
  try{
    const resp = await fetch('/transactions/new', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({type:'credit', recipient, amount, private_key: stored.private_key}),
    });
    const json = await resp.json().catch(()=>({}));
    if(!resp.ok){
      if(resp.status === 403){
        alert('Transaction refusée (403) : ' + (json.message || json.error || JSON.stringify(json)));
      }else{
        alert('Erreur : ' + (json.message || json.error || ('status ' + resp.status)));
      }
      return;
    }
    markStep('step_tx');
    await refresh();
    alert(json.message || 'Added');
  }catch(e){ console.error(e); alert('Erreur lors de l\'envoi de la transaction'); }
});

document.getElementById('tamper_submit').addEventListener('click', async ()=>{
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

document.getElementById('broadcast_tampered').addEventListener('click', async ()=>{
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

document.getElementById('resolve').addEventListener('click', async ()=>{
  try{
    const data = await api('/nodes/resolve');
    markStep('step_resolve');
    await refresh();
    alert(data.message || 'Resolved');
  }catch(e){ console.error(e) }
});

document.getElementById('reset_demo').addEventListener('click', async ()=>{
  if(!confirm('Reset demo to genesis state? This will clear the chain and logs.')) return;
  try{
    const data = await api('/reset','POST',{});
    markStep('step_reset');
    await refresh();
    alert(data.message || 'Reset');
  }catch(e){ console.error(e) }
});

document.getElementById('add_peer').addEventListener('click', async ()=>{
  const addr = document.getElementById('peer_addr').value.trim();
  if(!addr){ alert('Entrez l\'URL du pair, ex: http://localhost:5001'); return }
  try{
    const data = await api('/nodes/register','POST',{nodes:[addr]});
    await refresh();
    alert(data.message || 'Peer registered');
  }catch(e){ console.error(e); alert('Erreur registering peer') }
});

async function authorizeResponsable() {
if(!currentIdentity || currentRoleKey !== 'responsable') {
    alert('Vous devez être connecté en tant que responsable pour autoriser le responsable sur la chaîne'); 
    return;
  } 
  try{
    // ensure we don't double-authorize
    try{
      const ids = await ensureDemoIdentities();
      const auth = await api('/authorities');
      const authorities = auth.authorities || [];
      let responsableAddr = currentIdentity.address;
      if(responsableAddr && authorities.includes(responsableAddr)){
        alert('Le responsable est déjà autorisé — aucune action nécessaire.');
        return;
      }
    }catch(e){ }
    let addr = null;
    if(currentIdentity && currentRoleKey === 'responsable') addr = currentIdentity.address;
    if(!addr){
      try{ const remote = await api('/demo/roles'); addr = (remote.demo_roles || {}).responsable; }catch(e){}
    }
    if(!addr){ alert('Aucune adresse de responsable détectée'); return }

    // POST /authorities/register will add a registration transaction
    const reg = await api('/authorities/register','POST',{address: addr});
    // Try to mine the registration so it becomes effective (best-effort)
    try{
      const mine = await api('/mine');
      await refresh();
      alert(`Autorisation requêtée. Mine: ${mine.message || JSON.stringify(mine)}`);
    }catch(e){
      // mining may fail if node isn't allowed; still show registration message
      await refresh();
      alert(reg.message || 'Enregistré (en attente de minage)');
    }
  }catch(e){ console.error(e); alert('Erreur lors de l\'autorisation') }
}

document.getElementById('authorize_responsable').addEventListener('click', authorizeResponsable);

function markStep(id){
  document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));
  const el = document.getElementById(id);
  if(el) el.classList.add('active');
}

addChangeRoleButton();
const persisted = localStorage.getItem('ylia_demo_current_role');
if(persisted){
  ensureDemoIdentities().then(ids => {
    if(ids && ids[persisted]){
      setCurrentIdentity(ids, persisted);
      if(!pollingTimer){ pollingTimer = setInterval(refresh, POLL_INTERVAL); }
      refresh();
    }

    showRolePicker(false);
  }).catch(()=> showRolePicker());
}else{
  showRolePicker();
}
