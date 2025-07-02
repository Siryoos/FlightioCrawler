async function getHealth() {
    const r = await fetch('/health');
    const data = await r.json();
    document.getElementById('healthResult').textContent = JSON.stringify(data, null, 2);
}

async function getMetrics() {
    const r = await fetch('/metrics');
    const data = await r.json();
    document.getElementById('metricsResult').textContent = JSON.stringify(data, null, 2);
}

async function getStats() {
    const r = await fetch('/stats');
    const data = await r.json();
    document.getElementById('statsResult').textContent = JSON.stringify(data, null, 2);
}

async function resetStats() {
    const r = await fetch('/reset', {method: 'POST'});
    const data = await r.json();
    document.getElementById('statsResult').textContent = JSON.stringify(data, null, 2);
}

async function predictPrices(route, dates) {
    const params = new URLSearchParams();
    params.append('route', route);
    dates.forEach(d => params.append('dates', d));
    const r = await fetch('/predict?' + params.toString(), {method: 'POST'});
    const data = await r.json();
    document.getElementById('predictResult').textContent = JSON.stringify(data, null, 2);
}

async function intelligentSearch(query, options) {
    const params = new URLSearchParams({
        origin: query.origin,
        destination: query.destination,
        date: query.date,
        enable_multi_route: options.multiRoute,
        enable_date_range: options.dateRange,
        date_range_days: options.rangeDays
    });
    const r = await fetch('/search/intelligent?' + params.toString(), {method: 'POST'});
    const data = await r.json();
    document.getElementById('intelligentResult').textContent = JSON.stringify(data, null, 2);
}

let ws;

function connectWebSocket(userId) {
    if (ws) {
        ws.close();
    }
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws/prices/${encodeURIComponent(userId)}`);
    ws.onmessage = (event) => {
        const el = document.getElementById('wsResult');
        el.textContent += event.data + '\n';
    };
}

document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        origin: document.getElementById('origin').value,
        destination: document.getElementById('destination').value,
        date: document.getElementById('date').value
    };
    const r = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept-Language': document.getElementById('language').value },
        body: JSON.stringify(payload)
    });
    const data = await r.json();
    displaySearchResults(data.flights || []);
});

document.getElementById('predictForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const route = document.getElementById('predictRoute').value;
    const dates = document.getElementById('predictDates').value.split(',').map(d => d.trim()).filter(Boolean);
    await predictPrices(route, dates);
});

document.getElementById('intelligentForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = {
        origin: document.getElementById('intOrigin').value,
        destination: document.getElementById('intDestination').value,
        date: document.getElementById('intDate').value
    };
    const options = {
        multiRoute: document.getElementById('multiRoute').checked,
        dateRange: document.getElementById('dateRange').checked,
        rangeDays: document.getElementById('dateRangeDays').value
    };
    await intelligentSearch(query, options);
});

document.getElementById('connectWs').addEventListener('click', () => {
    const userId = document.getElementById('wsUserId').value || 'user1';
    connectWebSocket(userId);
});

function displaySearchResults(flights) {
    const container = document.getElementById('searchResult');
    container.innerHTML = '';
    if (!flights.length) {
        container.textContent = 'No results';
        return;
    }
    const table = document.createElement('table');
    const header = document.createElement('tr');
    Object.keys(flights[0]).forEach(k => {
        const th = document.createElement('th');
        th.textContent = k;
        header.appendChild(th);
    });
    table.appendChild(header);
    flights.forEach(f => {
        const row = document.createElement('tr');
        Object.values(f).forEach(v => {
            const td = document.createElement('td');
            td.textContent = v;
            row.appendChild(td);
        });
        table.appendChild(row);
    });
    container.appendChild(table);
}

document.getElementById('alertForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        user_id: document.getElementById('alertUser').value,
        route: document.getElementById('alertRoute').value,
        target_price: parseFloat(document.getElementById('alertPrice').value)
    };
    await fetch('/alerts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    loadAlerts();
});

async function loadAlerts() {
    const r = await fetch('/alerts');
    const data = await r.json();
    const list = document.getElementById('alertList');
    list.innerHTML = '';
    data.alerts.forEach(a => {
        const li = document.createElement('li');
        li.textContent = `${a.route} -> ${a.target_price}`;
        const btn = document.createElement('button');
        btn.textContent = 'Remove';
        btn.onclick = async () => {
            await fetch('/alerts/' + a.id, {method: 'DELETE'});
            loadAlerts();
        };
        li.appendChild(btn);
        list.appendChild(li);
    });
}

async function startMonitoring() {
    const routes = document.getElementById('monitorRoutes').value.split(',').map(r => r.trim()).filter(Boolean);
    await fetch('/monitor/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({routes})
    });
    updateMonitorStatus();
}

async function stopMonitoring() {
    await fetch('/monitor/stop', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({})});
    updateMonitorStatus();
}

async function updateMonitorStatus() {
    const r = await fetch('/monitor/status');
    const data = await r.json();
    document.getElementById('monitorStatus').textContent = data.monitoring.join(', ');
}

let trendChart;
async function showTrend() {
    const route = document.getElementById('trendRoute').value;
    const r = await fetch(`/trend/${route}`);
    const data = await r.json();
    const ctx = document.getElementById('trendChart').getContext('2d');
    const labels = data.chart_data.map(d => d.date);
    const prices = data.chart_data.map(d => d.price);
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets: [{ label: route, data: prices, fill: false, borderColor: 'blue' }] }
    });
}

updateMonitorStatus();
loadAlerts();
