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
