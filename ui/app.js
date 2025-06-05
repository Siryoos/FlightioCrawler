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
    ws = new WebSocket(`ws://${location.host}/ws/prices/${encodeURIComponent(userId)}`);
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await r.json();
    document.getElementById('searchResult').textContent = JSON.stringify(data, null, 2);
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
