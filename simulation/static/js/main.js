import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Configuration
const REFRESH_RATE = 0; // ms - no delay for maximum speed
const STEPS_PER_FRAME = 3; // Run multiple simulation steps per render frame
let pathsPerTest = 100; // Configurable pathfinding experiments per exploration test

// State
let isRunning = false;
let autoRunMode = false; // Auto-run exploration until complete
let totalExplorationTests = 10; // Number of exploration tests to run
let currentTestNumber = 0; // Current test (1-indexed when running)
let experimentsTriggered = false; // Prevent double-triggering within a test
let experimentsCompleted = 0; // Track completed experiments
let experimentProgressInterval = null; // Polling interval for experiment progress
let allTestResults = []; // Aggregate results across all tests
let scene, camera, renderer, controls;
let agentsMesh = [];
let obstaclesMesh = [];

let pathLines3D = { dijkstra: null, astar: null, safety: null, balanced: null, manual: null };
let nestMesh = null;
let mapCanvas, mapCtx;
let envDimensions = { width: 500, height: 500, depth: 500, resolution: 50 };
let nestPosition = { x: 0, y: 0, z: 250 };
let simulationStartTime = null;
let current2DExploration = 0; // Track 2D exploration percentage

// Exploration tracking (sector grid removed)

// 3D exploration visualization - fog of war style
let explorationGrid3D = null; // Grid of cells for exploration lighting
let explorationGridData = null; // Data tracking which cells are explored
let fogOfWarEnabled = true; // Toggle for fog visibility
const EXPLORATION_GRID_SIZE = 25; // 25x25x25 grid = 20 units per cell in 500x500x500 env
const AGENT_VISUAL_RANGE = 30; // Visual range radius for each agent
// Sector exploration threshold removed

// Experiment results storage
let currentExperimentData = null;
let currentExperimentRaw = null;

// Fitness tracking
let fitnessUpdateCounter = 0;

// Pathfinding State
let startPoint = null;
let goalPoint = null;
let dijkstraPath = [];
let astarPath = [];
let safetyPath = [];
let balancedPath = [];

// Manual Path State
let manualWaypoints = [];

// DOM Elements
const btnStop = document.getElementById('btn-stop');

// Stats Elements
const statOffensive = document.getElementById('stat-offensive');
const statNeutral = document.getElementById('stat-neutral');
const statDefensive = document.getElementById('stat-defensive');
const statTotal = document.getElementById('stat-total');
const statExploration = document.getElementById('stat-exploration');
const statFitness = document.getElementById('stat-fitness');
const statViolations = document.getElementById('stat-violations');
const swarmModeIndicator = document.getElementById('swarm-mode-indicator');
const swarmModeText = document.getElementById('swarm-mode-text');
const simStatusDot = document.getElementById('sim-status-dot');
const simStatusText = document.getElementById('sim-status-text');
const simTime = document.getElementById('sim-time');
const agentCountBadge = document.getElementById('agent-count-badge');

// Sector grid removed from DOM

// Path Legend
const pathLegend = document.getElementById('path-legend');

// Zoom Controls
const btnZoomIn = document.getElementById('btn-zoom-in');
const btnZoomOut = document.getElementById('btn-zoom-out');
const btnZoomReset = document.getElementById('btn-zoom-reset');
const btnFogToggle = document.getElementById('btn-fog-toggle');

// Progress Bar Elements
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');

// Welcome Screen Elements
const welcomeScreen = document.getElementById('welcome-screen');
const numExperimentsInput = document.getElementById('num-experiments');
const pathsPerTestInput = document.getElementById('paths-per-test');
const btnStartSession = document.getElementById('btn-start-session');
const dashboard = document.getElementById('dashboard');

// Initialize - wait for welcome screen interaction
function initWelcomeScreen() {
    btnStartSession.addEventListener('click', startSession);
    numExperimentsInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') startSession();
    });
    if (pathsPerTestInput) {
        pathsPerTestInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') startSession();
        });
    }
}

async function startSession() {
    totalExplorationTests = parseInt(numExperimentsInput.value) || 10;
    totalExplorationTests = Math.max(1, Math.min(100, totalExplorationTests));
    
    // Get paths per test from input
    if (pathsPerTestInput) {
        pathsPerTest = parseInt(pathsPerTestInput.value) || 100;
        pathsPerTest = Math.max(10, Math.min(500, pathsPerTest));
    }
    
    currentTestNumber = 0;
    allTestResults = [];
    autoRunMode = true;
    experimentsTriggered = false;
    
    // Hide welcome, show dashboard
    welcomeScreen.style.display = 'none';
    dashboard.style.display = 'grid';
    
    // Initialize the main app
    await init();
    
    // Start the first test cycle
    startNextTestCycle();
}

// Start the next test cycle (exploration + experiments)
async function startNextTestCycle() {
    currentTestNumber++;
    experimentsTriggered = false;
    current2DExploration = 0;
    
    console.log(`Starting exploration test ${currentTestNumber}/${totalExplorationTests}`);
    
    // Update progress bar immediately to show fresh start
    updateOverallProgressBar();
    
    // Always reset simulation for fresh random obstacles
    await fetch('/init', { method: 'POST' });
    await initializeNestPosition();
    
    // Clear 3D exploration grid
    clearExplorationGrid3D();
    
    // Clear 3D scene objects
    agentsMesh.forEach(mesh => scene.remove(mesh));
    agentsMesh = [];
    obstaclesMesh.forEach(mesh => scene.remove(mesh));
    obstaclesMesh = [];
    
    // Clear 2D map
    if (mapCtx && mapCanvas) {
        mapCtx.fillStyle = '#1a1a2e';
        mapCtx.fillRect(0, 0, mapCanvas.width, mapCanvas.height);
    }
    
    // Auto-start simulation immediately
    isRunning = true;
    btnStop.disabled = false;
    simStatusDot.classList.add('active');
    simStatusText.textContent = `Test ${currentTestNumber}/${totalExplorationTests} - Exploring...`;
    simulationStartTime = Date.now();
    loop();
}

// Clear the 3D exploration grid for a fresh test
function clearExplorationGrid3D() {
    if (explorationGridData) {
        for (let x = 0; x < EXPLORATION_GRID_SIZE; x++) {
            for (let y = 0; y < EXPLORATION_GRID_SIZE; y++) {
                for (let z = 0; z < EXPLORATION_GRID_SIZE; z++) {
                    explorationGridData[x][y][z] = 0;
                }
            }
        }
    }
    // Reset fog of war visibility - restore all cells to visible
    if (explorationInstancedMesh && explorationCellSize > 0) {
        let index = 0;
        for (let x = 0; x < EXPLORATION_GRID_SIZE; x++) {
            for (let y = 0; y < EXPLORATION_GRID_SIZE; y++) {
                for (let z = 0; z < EXPLORATION_GRID_SIZE; z++) {
                    tempMatrix.makeTranslation(
                        x * explorationCellSize + explorationCellSize / 2,
                        y * explorationCellSize + explorationCellSize / 2,
                        z * explorationCellSize + explorationCellSize / 2
                    );
                    explorationInstancedMesh.setMatrixAt(index, tempMatrix);
                    index++;
                }
            }
        }
        explorationInstancedMesh.instanceMatrix.needsUpdate = true;
    }
}

// Initialize
async function init() {
    init3D();
    init2D();
    setupEventListeners();
    setupModalEventListeners();
    // Don't fetch step here - startNextTestCycle will handle initialization
}

// Start welcome screen
initWelcomeScreen();

function init3D() {
    const container = document.getElementById('view-3d');

    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0d0d);

    // Camera
    camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 2000);
    camera.position.set(600, -200, 500);
    camera.up.set(0, 0, 1);

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // Controls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 100;
    controls.maxDistance = 1500;
    controls.target.set(250, 250, 250);
    controls.update();

    // Lights
    const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(300, 300, 400);
    scene.add(directionalLight);

    const redLight = new THREE.PointLight(0x8b0000, 0.5, 800);
    redLight.position.set(250, 250, 600);
    scene.add(redLight);

    // Grid Helper
    const gridHelper = new THREE.GridHelper(500, 25, 0x4a0000, 0x1a1a1a);
    gridHelper.rotation.x = Math.PI / 2;
    gridHelper.position.set(250, 250, 0);
    scene.add(gridHelper);

    // Environment Boundary Box
    const boundaryGeometry = new THREE.BoxGeometry(500, 500, 500);
    const boundaryEdges = new THREE.EdgesGeometry(boundaryGeometry);
    const boundaryMaterial = new THREE.LineBasicMaterial({ color: 0x8b0000, opacity: 0.5, transparent: true });
    const boundaryLine = new THREE.LineSegments(boundaryEdges, boundaryMaterial);
    boundaryLine.position.set(250, 250, 250);
    scene.add(boundaryLine);

    // Axes Helper
    const axesHelper = new THREE.AxesHelper(50);
    scene.add(axesHelper);

    // Initialize exploration fog-of-war grid
    initExplorationGrid();

    // Animation Loop
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    // Resize handler
    window.addEventListener('resize', () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });
}

function init2D() {
    mapCanvas = document.getElementById('map-canvas');
    mapCtx = mapCanvas.getContext('2d');

    // Use high resolution for crisp heatmap (4x CSS size)
    const container = document.getElementById('heatmap-canvas-container');
    const dpr = window.devicePixelRatio || 1;
    const canvasSize = Math.max(400, container.clientWidth * dpr * 2);
    mapCanvas.width = canvasSize;
    mapCanvas.height = canvasSize;
    mapCtx.imageSmoothingEnabled = false; // Crisp pixel edges
}

// Modal chart instance
let modalChart = null;

function displayExperimentResults(summary) {
    // Store the data for modal use
    currentExperimentData = summary;
    
    // Show the View Results button
    const btnViewResults = document.getElementById('btn-view-results');
    if (btnViewResults) {
        btnViewResults.style.display = 'block';
    }
    
    // Automatically open the modal
    openResultsModal();
}

function showExperimentResultsModal(summary) {
    // Store the summary as current experiment data
    currentExperimentData = summary;
    openResultsModal();
}

function openResultsModal() {
    const modal = document.getElementById('results-modal');
    modal.style.display = 'flex';
    
    (async () => {
        if (!currentExperimentData) {
            try {
                const st = await fetch('/experiments_status');
                const stj = await st.json();
                if (stj.json_available) {
                    const resp = await fetch('/experiment_json');
                    const text = await resp.text();
                    try {
                        const payload = JSON.parse(text);
                        currentExperimentRaw = payload;
                        currentExperimentData = parseJSONData(payload);
                    } catch (err) {
                        // Try to recover from non-standard tokens (Infinity/NaN)
                        try {
                            const fixed = text.replace(/\bInfinity\b/g, 'null').replace(/\bNaN\b/g, 'null');
                            const payload = JSON.parse(fixed);
                            console.warn('Recovered server JSON by replacing Infinity/NaN with null');
                            currentExperimentRaw = payload;
                            currentExperimentData = parseJSONData(payload);
                        } catch (err2) {
                            console.warn('Could not parse server JSON payload:', err2);
                        }
                    }
                }
            } catch (err) {
                console.warn('Could not fetch server JSON payload:', err);
            }
        }

        if (currentExperimentData) {
            updateModalVisualization('bar');
            updateModalStats();
        }
    })();
}

function closeResultsModal() {
    const modal = document.getElementById('results-modal');
    modal.style.display = 'none';
}

function updateModalStats() {
    if (!currentExperimentData) return;
    
    const summary = currentExperimentData;
    
    document.getElementById('modal-total-exp').textContent = summary.total_experiments || 30;
    
    // Find best algorithm by length
    const algorithms = ['dijkstra', 'astar', 'safety_first', 'balanced'];
    const algNames = { dijkstra: 'Dijkstra', astar: 'A*', safety_first: 'Safety First', balanced: 'Balanced' };
    
    let bestLength = Infinity, bestLengthAlg = '-';
    let bestCost = Infinity, bestCostAlg = '-';
    
    algorithms.forEach(alg => {
        if (summary[alg] && summary[alg].avg_length < bestLength) {
            bestLength = summary[alg].avg_length;
            bestLengthAlg = algNames[alg];
        }
        if (summary[alg] && summary[alg].avg_cost < bestCost) {
            bestCost = summary[alg].avg_cost;
            bestCostAlg = algNames[alg];
        }
    });
    
    document.getElementById('modal-best-length').textContent = bestLengthAlg;
    document.getElementById('modal-best-cost').textContent = bestCostAlg;
}

function updateModalVisualization(type) {
    const chartContainer = document.getElementById('modal-chart-container');
    const tableContainer = document.getElementById('modal-table-container');
    const statsPanel = document.getElementById('modal-stats');
    if (statsPanel) statsPanel.style.display = (type === 'hp' ? 'none' : 'block');
    
    if (type === 'table') {
        chartContainer.style.display = 'none';
        tableContainer.style.display = 'block';
        renderResultsTable();
        return;
    }
    
    chartContainer.style.display = 'block';
    tableContainer.style.display = 'none';
    
    if (!currentExperimentData) return;
    
    const summary = currentExperimentData;
    const ctx = document.getElementById('modal-chart').getContext('2d');
    
    if (modalChart) {
        modalChart.destroy();
    }
    
    const labels = ['Dijkstra', 'A*', 'Safety First', 'Balanced'];
    const colors = ['#8b0000', '#dc143c', '#ff4444', '#ff6b6b'];
    
    let chartConfig;
    
    if (type === 'bar') {
        chartConfig = {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Path Length',
                    data: [
                        summary.dijkstra?.avg_length || 0,
                        summary.astar?.avg_length || 0,
                        summary.safety_first?.avg_length || 0,
                        summary.balanced?.avg_length || 0
                    ],
                    backgroundColor: colors.map(c => c + '99'),
                    borderColor: colors,
                    borderWidth: 1
                }]
            },
            options: getChartOptions('Path Length')
        };
    } else if (type === 'bar-cost') {
        chartConfig = {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Path Cost',
                    data: [
                        summary.dijkstra?.avg_cost || 0,
                        summary.astar?.avg_cost || 0,
                        summary.safety_first?.avg_cost || 0,
                        summary.balanced?.avg_cost || 0
                    ],
                    backgroundColor: colors.map(c => c + '99'),
                    borderColor: colors,
                    borderWidth: 1
                }]
            },
            options: getChartOptions('Path Cost')
        };
    } else if (type === 'success') {
        const total = summary.total_experiments || 30;
        chartConfig = {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Success Rate %',
                    data: [
                        ((summary.dijkstra?.successes || 0) / total) * 100,
                        ((summary.astar?.successes || 0) / total) * 100,
                        ((summary.safety_first?.successes || 0) / total) * 100,
                        ((summary.balanced?.successes || 0) / total) * 100
                    ],
                    backgroundColor: colors.map(c => c + '99'),
                    borderColor: colors,
                    borderWidth: 1
                }]
            },
            options: getChartOptions('Success Rate (%)')
        };
    } else if (type === 'scatter') {
        chartConfig = {
            type: 'scatter',
            data: {
                datasets: labels.map((label, i) => ({
                    label: label,
                    data: [{
                        x: summary[['dijkstra', 'astar', 'safety_first', 'balanced'][i]]?.avg_length || 0,
                        y: summary[['dijkstra', 'astar', 'safety_first', 'balanced'][i]]?.avg_cost || 0
                    }],
                    backgroundColor: colors[i],
                    pointRadius: 10
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#888' } } },
                scales: {
                    x: { title: { display: true, text: 'Path Length', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                    y: { title: { display: true, text: 'Path Cost', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                }
            }
        };
    } else if (type === 'hp') {
        // HP mode: prefer using already-loaded JSON payload, otherwise fetch endpoint
        const statsPanel = document.getElementById('modal-stats');
        if (statsPanel) statsPanel.style.display = 'none';
        chartContainer.style.display = 'block';
        tableContainer.style.display = 'none';

        const chartArea = document.getElementById('modal-chart-container');
        chartArea.innerHTML = '<canvas id="modal-chart"></canvas>';

        // Prefer server-provided aggregated JSON payload if present
        if (currentExperimentRaw && currentExperimentRaw.hp_rl_results) {
            try {
                renderHPChart(currentExperimentRaw.hp_rl_results);
            } catch (err) {
                console.error('Error rendering HP chart from payload:', err);
                chartArea.innerHTML = '<div style="color:#f88;padding:1rem;">HP-RL results unavailable (render error)</div>';
            }
            return;
        }

        // Fallback: request the dedicated endpoint with graceful handling
        fetch('/hp_rl_results')
            .then(async r => {
                if (!r.ok) {
                    const txt = await r.text().catch(() => null);
                    console.warn('/hp_rl_results returned', r.status, txt);
                    throw new Error('HP-RL results unavailable');
                }
                return r.json();
            })
            .then(data => {
                renderHPChart(data);
            })
            .catch(err => {
                console.warn('HP-RL fetch error', err);
                chartArea.innerHTML = '<div style="color:#f88;padding:1rem;">HP-RL results unavailable</div>';
            });
        return;
    }
    
    modalChart = new Chart(ctx, chartConfig);
}

function getChartOptions(yLabel) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.1)' } },
            y: { title: { display: true, text: yLabel, color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.1)' } }
        }
    };
}

function renderResultsTable() {
    if (!currentExperimentData) return;
    
    const summary = currentExperimentData;
    const total = summary.total_experiments || 30;
    
    document.getElementById('modal-table-container').innerHTML = `
        <table class="exp-results-table">
            <thead>
                <tr><th>Algorithm</th><th>Avg Length</th><th>Avg Cost</th><th>Success Rate</th><th>Successes</th></tr>
            </thead>
            <tbody>
                <tr style="border-left: 3px solid #00ff00;">
                    <td>Dijkstra</td>
                    <td>${(summary.dijkstra?.avg_length || 0).toFixed(1)}</td>
                    <td>${(summary.dijkstra?.avg_cost || 0).toFixed(2)}</td>
                    <td>${(((summary.dijkstra?.successes || 0) / total) * 100).toFixed(1)}%</td>
                    <td>${summary.dijkstra?.successes || 0}/${total}</td>
                </tr>
                <tr style="border-left: 3px solid #ff00ff;">
                    <td>A*</td>
                    <td>${(summary.astar?.avg_length || 0).toFixed(1)}</td>
                    <td>${(summary.astar?.avg_cost || 0).toFixed(2)}</td>
                    <td>${(((summary.astar?.successes || 0) / total) * 100).toFixed(1)}%</td>
                    <td>${summary.astar?.successes || 0}/${total}</td>
                </tr>
                <tr style="border-left: 3px solid #00bfff;">
                    <td>Safety First</td>
                    <td>${(summary.safety_first?.avg_length || 0).toFixed(1)}</td>
                    <td>${(summary.safety_first?.avg_cost || 0).toFixed(2)}</td>
                    <td>${(((summary.safety_first?.successes || 0) / total) * 100).toFixed(1)}%</td>
                    <td>${summary.safety_first?.successes || 0}/${total}</td>
                </tr>
                <tr style="border-left: 3px solid #ffa500;">
                    <td>Balanced</td>
                    <td>${(summary.balanced?.avg_length || 0).toFixed(1)}</td>
                    <td>${(summary.balanced?.avg_cost || 0).toFixed(2)}</td>
                    <td>${(((summary.balanced?.successes || 0) / total) * 100).toFixed(1)}%</td>
                    <td>${summary.balanced?.successes || 0}/${total}</td>
                </tr>
            </tbody>
        </table>
    `;
}

function renderHPResults(data) {
    const container = document.getElementById('modal-table-container');
    if (!data) {
        container.innerHTML = '<p>No HP-RL results available.</p>';
        return;
    }

    // Agent average rewards
    let html = '<h3>Boids HP-RL Evaluation</h3>';
    html += '<h4>Average Rewards</h4>';
    html += '<table class="exp-results-table"><thead><tr><th>Agent</th><th>Profile</th><th>Avg Reward</th></tr></thead><tbody>';
    const profiles = data.agent_profiles || [];
    for (const [id, reward] of Object.entries(data.avg_agent_rewards || {})) {
        const profile = profiles[id] || 'Unknown';
        html += `<tr><td>Agent ${id}</td><td>${profile}</td><td>${reward.toFixed(2)}</td></tr>`;
    }
    html += `<tr style="font-weight:bold;"><td>Swarm</td><td>-</td><td>${(data.avg_swarm_reward || 0).toFixed(2)}</td></tr>`;
    html += '</tbody></table>';

    // Use backend-provided per-profile summary when available, otherwise derive from policies
    let perProfileSummary = data.per_profile || {};
    if (!data.per_profile) {
        perProfileSummary = {};
        const perProfile = {};
        const policies = data.policies || {};
        Object.entries(policies).forEach(([aid, policy]) => {
            const profile = (profiles[aid] || 'Neutral');
            let top = null;
            Object.entries(policy).forEach(([s, info]) => {
                if (!top || info.q_value > top.q_value) top = info;
            });
            if (!top) return;
            if (!perProfile[profile]) perProfile[profile] = { count: 0, sum_ms: 0, sum_ma: 0, sum_mc: 0 };
            perProfile[profile].count += 1;
            perProfile[profile].sum_ms += top.multipliers[0];
            perProfile[profile].sum_ma += top.multipliers[1];
            perProfile[profile].sum_mc += top.multipliers[2];
        });

        Object.entries(perProfile).forEach(([p, val]) => {
            perProfileSummary[p] = {
                avg_multipliers: [val.sum_ms / val.count, val.sum_ma / val.count, val.sum_mc / val.count],
                avg_weights: [0,0,0],
                count: val.count
            };
        });
    }

    html += '<h4>Aggregated Best Multipliers (per profile)</h4>';
    html += '<table class="exp-results-table"><thead><tr><th>Profile</th><th>avg ms (cohesion x)</th><th>avg ma (alignment x)</th><th>avg mc (separation x)</th><th>sample_size</th></tr></thead><tbody>';
    Object.entries(perProfileSummary).forEach(([p, val]) => {
        const avg_ms = (val.avg_multipliers[0]).toFixed(2);
        const avg_ma = (val.avg_multipliers[1]).toFixed(2);
        const avg_mc = (val.avg_multipliers[2]).toFixed(2);
        html += `<tr><td>${p}</td><td>${avg_ms}</td><td>${avg_ma}</td><td>${avg_mc}</td><td>${val.count || '-'}</td></tr>`;
    });
    html += '</tbody></table>';

    // Show sample of per-agent optimal-policy entries
    html += '<h4>Sample Optimal Policy (per agent, top states)</h4>';
    Object.entries(data.policies || {}).forEach(([aid, policy]) => {
        html += `<div style="margin-top:8px;font-weight:700;">Agent ${aid} (profile: ${profiles[aid] || 'N/A'})</div>`;
        html += '<table class="exp-results-table"><thead><tr><th>State</th><th>ms,ma,mc</th><th>Q</th></tr></thead><tbody>';
        const entries = Object.entries(policy).map(([s, info]) => ({ s, ...info }));
        entries.sort((a, b) => b.q_value - a.q_value);
        entries.slice(0, 8).forEach(e => {
            html += `<tr><td>${e.s}</td><td>${e.multipliers.map(x => x.toFixed(2)).join(', ')}</td><td>${e.q_value.toFixed(2)}</td></tr>`;
        });
        html += '</tbody></table>';
    });

    container.innerHTML = html;
}

function renderHPChart(data) {
    const ctx = document.getElementById('modal-chart').getContext('2d');
    if (modalChart) modalChart.destroy();

    // Prefer backend-provided per_profile summary; fallback to frontend aggregation
    const perProfile = data.per_profile || {};
    const profilesOrder = ['Defensive', 'Neutral', 'Offensive'];

    const cohesionVals = profilesOrder.map(p => (perProfile[p]?.avg_weights ? perProfile[p].avg_weights[0] : (perProfile[p]?.avg_multipliers ? (perProfile[p].avg_multipliers[0]) : 0)) );
    const alignmentVals = profilesOrder.map(p => (perProfile[p]?.avg_weights ? perProfile[p].avg_weights[1] : (perProfile[p]?.avg_multipliers ? (perProfile[p].avg_multipliers[1]) : 0)) );
    const separationVals = profilesOrder.map(p => (perProfile[p]?.avg_weights ? perProfile[p].avg_weights[2] : (perProfile[p]?.avg_multipliers ? (perProfile[p].avg_multipliers[2]) : 0)) );

    // If backend returned multipliers instead of absolute weights for a profile, the values above will be multipliers.
    // We expect per_profile.avg_weights to be present; if not, the chart will show multipliers.

    modalChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: profilesOrder,
            datasets: [
                { label: 'Cohesion (w_c)', data: cohesionVals, backgroundColor: '#8b0000' },
                { label: 'Alignment (w_a)', data: alignmentVals, backgroundColor: '#dc143c' },
                { label: 'Separation (w_s)', data: separationVals, backgroundColor: '#ff4444' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top', labels: { color: '#ccc' } } },
            scales: {
                x: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.03)' } },
                y: { title: { display: true, text: 'Weight / Multiplier', color: '#888' }, ticks: { color: '#888' }, beginAtZero: true }
            }
        }
    });
}

function parseCSVData(csvText) {
    // Handle both Windows (\r\n) and Unix (\n) line endings
    const lines = csvText.trim().replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
    if (lines.length < 2) return null;
    
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/"/g, ''));
    
    // Initialize summary structure
    const summary = {
        total_experiments: 0,
        dijkstra: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 },
        astar: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 },
        safety_first: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 },
        balanced: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 }
    };
    
    // Find column indices for new CSV format (columns per algorithm)
    const findCol = (name) => headers.findIndex(h => h === name || h.includes(name));

    const dijkSuccessIdx = findCol('dijkstra_success');
    const dijkLengthIdx = findCol('dijkstra_path_length');
    const dijkCostIdx = findCol('dijkstra_cost');
    
    const astarSuccessIdx = findCol('astar_success');
    const astarLengthIdx = findCol('astar_path_length');
    const astarCostIdx = findCol('astar_cost');
    
    const safetySuccessIdx = findCol('safety_success');
    const safetyLengthIdx = findCol('safety_path_length');
    const safetyCostIdx = findCol('safety_cost');
    
    const balancedSuccessIdx = findCol('balanced_success');
    const balancedLengthIdx = findCol('balanced_path_length');
    const balancedCostIdx = findCol('balanced_cost');
    
    // Parse each row
    for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
        if (values.length < 5) continue; // Skip incomplete rows
        
        summary.total_experiments++;        
        // Parse A*
        if (astarSuccessIdx >= 0) {
            const success = values[astarSuccessIdx] === '1' || values[astarSuccessIdx].toLowerCase() === 'true';
            const length = parseFloat(values[astarLengthIdx]) || 0;
            const cost = parseFloat(values[astarCostIdx]) || 0;
            if (success && cost >= 0) {
                summary.astar.successes++;
                summary.astar.total_length += length;
                summary.astar.total_cost += cost;
                summary.astar.count++;
            }
        }
        
        // Parse Safety First
        if (safetySuccessIdx >= 0) {
            const success = values[safetySuccessIdx] === '1' || values[safetySuccessIdx].toLowerCase() === 'true';
            const length = parseFloat(values[safetyLengthIdx]) || 0;
            const cost = parseFloat(values[safetyCostIdx]) || 0;
            if (success && cost >= 0) {
                summary.safety_first.successes++;
                summary.safety_first.total_length += length;
                summary.safety_first.total_cost += cost;
                summary.safety_first.count++;
            }
        }
        
        // Parse Balanced
        if (balancedSuccessIdx >= 0) {
            const success = values[balancedSuccessIdx] === '1' || values[balancedSuccessIdx].toLowerCase() === 'true';
            const length = parseFloat(values[balancedLengthIdx]) || 0;
            const cost = parseFloat(values[balancedCostIdx]) || 0;
            if (success && cost >= 0) {
                summary.balanced.successes++;
                summary.balanced.total_length += length;
                summary.balanced.total_cost += cost;
                summary.balanced.count++;
            }
        }
    }
    
    // Calculate averages
    ['dijkstra', 'astar', 'safety_first', 'balanced'].forEach(alg => {
        if (summary[alg].count > 0) {
            summary[alg].avg_length = summary[alg].total_length / summary[alg].count;
            summary[alg].avg_cost = summary[alg].total_cost / summary[alg].count;
        }
    });
    
    return summary;
}

function parseJSONData(obj) {
    // Accept two shapes: { aggregated_results: [...], hp_rl_results: {...} }
    const experiments = (obj && obj.aggregated_results) ? obj.aggregated_results : (Array.isArray(obj) ? obj : []);

    const summary = {
        total_experiments: 0,
        dijkstra: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 },
        astar: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 },
        safety_first: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 },
        balanced: { avg_length: 0, avg_cost: 0, successes: 0, total_length: 0, total_cost: 0, count: 0 }
    };

    experiments.forEach(exp => {
        summary.total_experiments++;
        const res = exp.results || exp.results || {};

        ['dijkstra','astar','safety_first','balanced'].forEach(alg => {
            const a = res[alg];
            if (!a) return;
            const success = a.success === true || a.success === 1 || a.success === '1';
            const length = Number(a.path_length) || 0;
            const cost = (a.cost === undefined || a.cost === null) ? NaN : Number(a.cost);
            if (success && !isNaN(cost) && cost >= 0) {
                summary[alg].successes++;
                summary[alg].total_length += length;
                summary[alg].total_cost += cost;
                summary[alg].count++;
            }
        });
    });

    ['dijkstra','astar','safety_first','balanced'].forEach(alg => {
        if (summary[alg].count > 0) {
            summary[alg].avg_length = summary[alg].total_length / summary[alg].count;
            summary[alg].avg_cost = summary[alg].total_cost / summary[alg].count;
        }
    });

    // Attach hp_rl_results if present
    if (obj && obj.hp_rl_results) summary.hp_rl_results = obj.hp_rl_results;

    return summary;
}

function setupModalEventListeners() {
    // Close modal
    const btnCloseModal = document.getElementById('btn-close-modal');
    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', closeResultsModal);
    }
    
    // View results button
    const btnViewResults = document.getElementById('btn-view-results');
    if (btnViewResults) {
        btnViewResults.addEventListener('click', openResultsModal);
    }
    
    // View statistics button (static button in controls)
    const btnViewStats = document.getElementById('btn-view-stats');
    if (btnViewStats) {
        btnViewStats.addEventListener('click', openResultsModal);
    }
    
    // Click outside modal to close
    const modal = document.getElementById('results-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeResultsModal();
            }
        });
    }
    
    // Visualization type selector
    const vizTypeSelect = document.getElementById('viz-type-select');
    if (vizTypeSelect) {
        vizTypeSelect.addEventListener('change', (e) => {
            updateModalVisualization(e.target.value);
        });
    }
    
    // CSV/JSON upload
    const csvUpload = document.getElementById('csv-upload');
    if (csvUpload) {
        csvUpload.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (evt) => {
                    try {
                                if (file.name.toLowerCase().endsWith('.json') || file.type.includes('json')) {
                                    let parsed = null;
                                    try {
                                        parsed = JSON.parse(evt.target.result);
                                    } catch (err) {
                                        // Attempt to fix common non-standard tokens produced by Python's json
                                        try {
                                            const fixed = evt.target.result.replace(/\bInfinity\b/g, 'null').replace(/\bNaN\b/g, 'null');
                                            parsed = JSON.parse(fixed);
                                            console.warn('Recovered JSON upload by replacing Infinity/NaN with null');
                                        } catch (err2) {
                                            throw err2 || err;
                                        }
                                    }
                                    const jsonSummary = parseJSONData(parsed);
                                    currentExperimentData = jsonSummary;
                                    // Keep raw payload available if hp results needed
                                    currentExperimentRaw = parsed;
                                } else {
                            const csvData = parseCSVData(evt.target.result);
                            if (csvData) {
                                currentExperimentData = csvData;
                            } else {
                                alert('Could not parse CSV file. Please check the format.');
                                return;
                            }
                        }
                        updateModalVisualization(vizTypeSelect.value);
                        updateModalStats();
                    } catch (err) {
                        console.error('Failed to parse uploaded file:', err);
                        alert('Failed to parse file. See console for details.');
                    }
                };
                reader.readAsText(file);
            }
        });
    }
}

async function initializeNestPosition() {
    // Try to fetch nest position from backend
    try {
        const response = await fetch('/get_nest_position');
        const data = await response.json();
        if (!data.error) {
            nestPosition = { x: data.x, y: data.y, z: data.z };
        } else {
            // Fallback: Generate random nest position at an edge
            const edges = ['left', 'right', 'top', 'bottom'];
            const edge = edges[Math.floor(Math.random() * edges.length)];
            
            switch(edge) {
                case 'left':
                    nestPosition = { x: 10, y: Math.random() * 500, z: 250 };
                    break;
                case 'right':
                    nestPosition = { x: 490, y: Math.random() * 500, z: 250 };
                    break;
                case 'top':
                    nestPosition = { x: Math.random() * 500, y: 490, z: 250 };
                    break;
                case 'bottom':
                    nestPosition = { x: Math.random() * 500, y: 10, z: 250 };
                    break;
            }
        }
    } catch (error) {
        console.error('Failed to fetch nest position:', error);
        // Fallback
        nestPosition = { x: 10, y: 250, z: 250 };
    }
    
    updateNestDisplay();
    createNestMesh();
}

function createNestMesh() {
    if (nestMesh) {
        scene.remove(nestMesh);
    }
    
    // Create nest indicator in 3D - smaller size
    const geometry = new THREE.ConeGeometry(6, 12, 6);
    const material = new THREE.MeshPhongMaterial({ 
        color: 0x8b0000, 
        emissive: 0x4a0000,
        shininess: 100 
    });
    nestMesh = new THREE.Mesh(geometry, material);
    nestMesh.position.set(nestPosition.x, nestPosition.y, nestPosition.z);
    nestMesh.rotation.x = Math.PI; // Point down
    scene.add(nestMesh);
}

function updateNestDisplay() {
    // Nest coord display was removed from UI - function kept for compatibility
}

// Fog-of-war exploration visualization - black cells hide unexplored areas
let explorationInstancedMesh = null;
const tempMatrix = new THREE.Matrix4();
const zeroScale = new THREE.Matrix4().makeScale(0, 0, 0);
let explorationCellSize = 0;

function initExplorationGrid() {
    // Create a 3D grid tracking exploration state
    explorationGridData = new Array(EXPLORATION_GRID_SIZE).fill(null).map(() =>
        new Array(EXPLORATION_GRID_SIZE).fill(null).map(() =>
            new Array(EXPLORATION_GRID_SIZE).fill(0) // 0 = unexplored, 1 = explored
        )
    );
    
    explorationCellSize = 500 / EXPLORATION_GRID_SIZE;
    const totalCells = EXPLORATION_GRID_SIZE * EXPLORATION_GRID_SIZE * EXPLORATION_GRID_SIZE;
    
    // Use InstancedMesh - black opaque cells that hide unexplored areas
    const cellGeometry = new THREE.BoxGeometry(explorationCellSize, explorationCellSize, explorationCellSize);
    const cellMaterial = new THREE.MeshBasicMaterial({
        color: 0x000000,
        transparent: false,
        depthWrite: true
    });
    
    explorationInstancedMesh = new THREE.InstancedMesh(cellGeometry, cellMaterial, totalCells);
    explorationInstancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    
    // Set up positions for all instances (full coverage, no gaps)
    let index = 0;
    for (let x = 0; x < EXPLORATION_GRID_SIZE; x++) {
        for (let y = 0; y < EXPLORATION_GRID_SIZE; y++) {
            for (let z = 0; z < EXPLORATION_GRID_SIZE; z++) {
                tempMatrix.makeTranslation(
                    x * explorationCellSize + explorationCellSize / 2,
                    y * explorationCellSize + explorationCellSize / 2,
                    z * explorationCellSize + explorationCellSize / 2
                );
                explorationInstancedMesh.setMatrixAt(index, tempMatrix);
                index++;
            }
        }
    }
    
    explorationInstancedMesh.instanceMatrix.needsUpdate = true;
    scene.add(explorationInstancedMesh);
    explorationGrid3D = explorationInstancedMesh; // Keep reference for reset
}

function updateExplorationFromAgents(agentsData) {
    if (!explorationInstancedMesh || !explorationGridData) return;
    
    const cellSize = explorationCellSize;
    const visualRangeCells = Math.ceil(AGENT_VISUAL_RANGE / cellSize);
    let needsMatrixUpdate = false;
    
    // For each agent, mark nearby cells as explored (remove black cover)
    agentsData.forEach(agent => {
        const gridX = Math.floor(agent.x / cellSize);
        const gridY = Math.floor(agent.y / cellSize);
        const gridZ = Math.floor(agent.z / cellSize);
        
        // Check cells within visual range
        for (let dx = -visualRangeCells; dx <= visualRangeCells; dx++) {
            for (let dy = -visualRangeCells; dy <= visualRangeCells; dy++) {
                for (let dz = -visualRangeCells; dz <= visualRangeCells; dz++) {
                    const cx = gridX + dx;
                    const cy = gridY + dy;
                    const cz = gridZ + dz;
                    
                    // Check bounds
                    if (cx < 0 || cx >= EXPLORATION_GRID_SIZE ||
                        cy < 0 || cy >= EXPLORATION_GRID_SIZE ||
                        cz < 0 || cz >= EXPLORATION_GRID_SIZE) continue;
                    
                    // Check if within visual range (spherical)
                    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) * cellSize;
                    if (dist <= AGENT_VISUAL_RANGE) {
                        // Mark as explored - remove the black cell
                        if (explorationGridData[cx][cy][cz] === 0) {
                            explorationGridData[cx][cy][cz] = 1;
                            
                            // Scale cell to 0 to hide it
                            const cellIndex = cx * EXPLORATION_GRID_SIZE * EXPLORATION_GRID_SIZE + 
                                             cy * EXPLORATION_GRID_SIZE + cz;
                            explorationInstancedMesh.setMatrixAt(cellIndex, zeroScale);
                            needsMatrixUpdate = true;
                        }
                    }
                }
            }
        }
    });
    
    // Only update GPU buffer if matrices changed
    if (needsMatrixUpdate) {
        explorationInstancedMesh.instanceMatrix.needsUpdate = true;
    }
}

function resetExplorationGrid() {
    if (!explorationInstancedMesh || !explorationGridData) return;
    
    // Reset all cells to unexplored - restore black cover
    let index = 0;
    for (let x = 0; x < EXPLORATION_GRID_SIZE; x++) {
        for (let y = 0; y < EXPLORATION_GRID_SIZE; y++) {
            for (let z = 0; z < EXPLORATION_GRID_SIZE; z++) {
                explorationGridData[x][y][z] = 0;
                tempMatrix.makeTranslation(
                    x * explorationCellSize + explorationCellSize / 2,
                    y * explorationCellSize + explorationCellSize / 2,
                    z * explorationCellSize + explorationCellSize / 2
                );
                explorationInstancedMesh.setMatrixAt(index, tempMatrix);
                index++;
            }
        }
    }
    explorationInstancedMesh.instanceMatrix.needsUpdate = true;
}

// Sector exploration calculation removed; visualization retained in 3D fog

function setupEventListeners() {
    // Simulation controls - start is automatic, no start button needed

    btnStop.addEventListener('click', () => {
        if (isRunning) {
            // Pause simulation
            isRunning = false;
            simStatusDot.classList.remove('active');
            simStatusDot.classList.add('idle');
            simStatusText.textContent = 'Paused';
            btnStop.textContent = 'Resume';
            btnStop.classList.remove('btn-danger');
            btnStop.classList.add('btn-primary');
        } else {
            // Resume simulation
            isRunning = true;
            simStatusDot.classList.add('active');
            simStatusDot.classList.remove('idle');
            simStatusText.textContent = 'Exploring...';
            btnStop.textContent = 'Pause';
            btnStop.classList.remove('btn-primary');
            btnStop.classList.add('btn-danger');
            loop();
        }
    });

    // Map click for pathfinding
    mapCanvas.addEventListener('click', (event) => {
        handleMapClick(event);
    });

    // Zoom controls
    btnZoomIn.addEventListener('click', () => {
        const distance = camera.position.distanceTo(controls.target);
        const newDistance = Math.max(distance * 0.8, 100); // Zoom in 20%, min 100
        const direction = camera.position.clone().sub(controls.target).normalize();
        camera.position.copy(controls.target).add(direction.multiplyScalar(newDistance));
    });

    btnZoomOut.addEventListener('click', () => {
        const distance = camera.position.distanceTo(controls.target);
        const newDistance = Math.min(distance * 1.25, 1500); // Zoom out 25%, max 1500
        const direction = camera.position.clone().sub(controls.target).normalize();
        camera.position.copy(controls.target).add(direction.multiplyScalar(newDistance));
    });

    btnZoomReset.addEventListener('click', () => {
        camera.position.set(600, -200, 500);
        controls.target.set(250, 250, 250);
        controls.update();
    });

    // The Veil(the 100 refference) toggle
    btnFogToggle.addEventListener('click', () => {
        fogOfWarEnabled = !fogOfWarEnabled;
        if (explorationInstancedMesh) {
            explorationInstancedMesh.visible = fogOfWarEnabled;
        }
        btnFogToggle.style.opacity = fogOfWarEnabled ? '1' : '0.5';
        btnFogToggle.title = fogOfWarEnabled ? 'Hide The Veil' : 'Show The Veil';
    });
}

async function loop() {
    if (!isRunning) return;

    // Run multiple steps per frame for faster simulation
    for (let i = 0; i < STEPS_PER_FRAME; i++) {
        await fetchStep();
        if (!isRunning) break;
    }
    updateSimulationTime();

    // Use requestAnimationFrame for smooth rendering, setTimeout for stepping
    if (REFRESH_RATE <= 0) {
        requestAnimationFrame(loop);
    } else {
        setTimeout(loop, REFRESH_RATE);
    }
}

function updateSimulationTime() {
    if (simulationStartTime) {
        const elapsed = Math.floor((Date.now() - simulationStartTime) / 1000);
        const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
        const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        simTime.textContent = `T+ ${hours}:${minutes}:${seconds}`;
    }
}

async function fetchStep() {
    try {
        const response = await fetch('/step');
        const data = await response.json();
        updateState(data);
    } catch (error) {
        console.error('Error fetching step:', error);
        isRunning = false;
        btnStop.disabled = true;
        simStatusDot.classList.remove('active');
        simStatusDot.classList.add('error');
        simStatusText.textContent = 'Error';
    }
}

function updateState(data) {
    if (data.dimensions) {
        envDimensions = data.dimensions;
    }

    // Update stats
    const dist = data.stats.distribution;
    statOffensive.textContent = dist.Offensive;
    statNeutral.textContent = dist.Neutral;
    statDefensive.textContent = dist.Defensive;
    statTotal.textContent = data.agents.length;
    current2DExploration = data.stats.progress;
    statExploration.textContent = current2DExploration.toFixed(1) + '%';
    agentCountBadge.textContent = `${data.agents.length} Agents`;

    // Update progress bar
    updateProgressBar();

    // Check if 2D exploration is complete and auto-run experiments
    if (autoRunMode && current2DExploration >= 100.0 && !experimentsTriggered) {
        experimentsTriggered = true;
        triggerAutoExperiments();
    }

    // Determine swarm mode
    const total = dist.Offensive + dist.Neutral + dist.Defensive;
    let dominantMode = 'neutral';
    let dominantCount = dist.Neutral;
    
    if (dist.Offensive > dominantCount) {
        dominantMode = 'offensive';
        dominantCount = dist.Offensive;
    }
    if (dist.Defensive > dominantCount) {
        dominantMode = 'defensive';
    }

    updateSwarmMode(dominantMode);

    // Sector exploration grid removed from UI
    updateStopButtonState();

    // Update fitness stats
    updateFitnessStats();

    // Update 3D scene with agent-based exploration visualization
    updateAgents3D(data.agents);
    updateExplorationFromAgents(data.agents);
    updateObstacles3D(data.obstacles);

    // Update 2D map
    updateMap2D(data.explored_grid, data.threat_map, data.agents, data.obstacles);
}

// Auto-trigger experiments when 2D exploration is complete
async function triggerAutoExperiments() {
    console.log(`Test ${currentTestNumber}/${totalExplorationTests}: Running ${pathsPerTest} pathfinding experiments...`);
    
    // Stop simulation loop during experiments
    isRunning = false;
    
    // Calculate current 3D exploration percentage
    const exploration3DPct = calculate3DExplorationPercentage();
    
    // Update status
    simStatusText.textContent = `Test ${currentTestNumber}/${totalExplorationTests} - Running Experiments...`;
    simStatusDot.classList.remove('active');
    simStatusDot.classList.add('running-experiments');
    
    // Start polling for experiment progress
    experimentProgressInterval = setInterval(async () => {
        try {
            const progressResp = await fetch('/experiment_progress');
            const progressData = await progressResp.json();
            updateExperimentProgressBar(progressData);
        } catch (e) {
            console.error('Progress poll error:', e);
        }
    }, 100);
    
    try {
        const response = await fetch('/run_experiments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                num_experiments: pathsPerTest,
                exploration_3d_pct: exploration3DPct,
                test_number: currentTestNumber,
                total_tests: totalExplorationTests
            })
        });
        
        // Stop polling
        if (experimentProgressInterval) {
            clearInterval(experimentProgressInterval);
            experimentProgressInterval = null;
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Store results for aggregation
            allTestResults.push({
                testNumber: currentTestNumber,
                exploration3D: exploration3DPct,
                summary: data.summary,
                results: data.results_count || pathsPerTest * 4 // 4 profiles
            });
            
            // Check if more tests remaining
            if (currentTestNumber < totalExplorationTests) {
                // Update progress and start next cycle
                updateOverallProgressBar();
                simStatusText.textContent = `Test ${currentTestNumber} complete. Starting next...`;
                
                // Short delay then start next cycle
                setTimeout(() => {
                    startNextTestCycle();
                }, 500);
            } else {
                // All tests complete!
                finishAllTests(data);
            }
        } else {
            console.error('Experiments failed:', data.error);
            simStatusText.textContent = 'Experiment Error';
        }
    } catch (error) {
        if (experimentProgressInterval) {
            clearInterval(experimentProgressInterval);
            experimentProgressInterval = null;
        }
        console.error('Experiments error:', error);
        simStatusText.textContent = 'Experiment Error';
    }
}

// Called when all test cycles are complete
function finishAllTests(lastData) {
    btnStop.disabled = true;
    simStatusDot.classList.remove('active', 'running-experiments');
    simStatusDot.classList.add('complete');
    simStatusText.textContent = 'All Tests Complete!';
    
    // Update progress bar to show full completion
    if (progressBar) progressBar.style.width = '100%';
    const totalPaths = totalExplorationTests * pathsPerTest * 4; // 4 profiles
    if (progressText) progressText.textContent = `Complete! ${totalExplorationTests} tests × ${pathsPerTest} paths = ${totalPaths} total experiments`;
    
    // Show results modal with aggregated data
    currentExperimentData = lastData;
    showExperimentResultsModal(lastData.summary);
    
    // Auto-download aggregated CSV
    window.location.href = '/download_experiment_csv';
}

// Update overall progress bar across all tests
function updateOverallProgressBar() {
    if (!progressBar || !progressText) return;
    
    // Calculate overall progress: completed tests + current exploration progress
    const completedTests = currentTestNumber - 1;
    const currentExplorationProgress = Math.min(current2DExploration, 100) / 100;
    const totalProgress = ((completedTests + currentExplorationProgress * 0.5) / totalExplorationTests) * 100;
    
    progressBar.style.width = Math.min(totalProgress, 100) + '%';
    progressText.textContent = `Test ${currentTestNumber}/${totalExplorationTests} | Mapping: ${current2DExploration.toFixed(1)}%`;
}

// Update progress bar during experiments
function updateExperimentProgressBar(progressData) {
    if (!progressBar || !progressText) return;
    
    // Calculate overall progress including completed tests
    const completedTests = currentTestNumber - 1;
    const experimentProgress = (progressData.percentage || 0) / 100;
    // Each test is 50% exploration + 50% experiments
    const totalProgress = ((completedTests + 0.5 + experimentProgress * 0.5) / totalExplorationTests) * 100;
    
    progressBar.style.width = Math.min(totalProgress, 100) + '%';
    progressText.textContent = `Test ${currentTestNumber}/${totalExplorationTests} | Paths: ${progressData.current}/${progressData.total}`;
}

// Calculate 3D exploration percentage from grid data
function calculate3DExplorationPercentage() {
    if (!explorationGridData) return 0;
    
    let totalCells = 0;
    let exploredCells = 0;
    
    for (let x = 0; x < EXPLORATION_GRID_SIZE; x++) {
        for (let y = 0; y < EXPLORATION_GRID_SIZE; y++) {
            for (let z = 0; z < EXPLORATION_GRID_SIZE; z++) {
                totalCells++;
                if (explorationGridData[x][y][z] === 1) {
                    exploredCells++;
                }
            }
        }
    }
    
    return totalCells > 0 ? (exploredCells / totalCells) * 100 : 0;
}

// Update progress bar
function updateProgressBar() {
    if (!progressBar || !progressText) return;
    
    // Use overall progress bar for multi-test tracking
    updateOverallProgressBar();
}

function updateSwarmMode(mode) {
    swarmModeIndicator.className = 'swarm-mode ' + mode;
    swarmModeText.textContent = mode.toUpperCase();
}

// Sector grid UI removed; no DOM updates required

function updateStopButtonState() {
    if (current2DExploration >= 100.0 && isRunning) {
        btnStop.textContent = '✓ Complete';
        btnStop.classList.remove('btn-danger');
        btnStop.classList.add('btn-success');
    } else if (isRunning) {
        btnStop.textContent = '⏸ Pause';
        btnStop.classList.remove('btn-success');
        btnStop.classList.add('btn-danger');
    }
}

function updateAgents3D(agentsData) {
    while (agentsMesh.length < agentsData.length) {
        const geometry = new THREE.SphereGeometry(4, 16, 16);
        const material = new THREE.MeshPhongMaterial({ color: 0x00ffff });
        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);
        agentsMesh.push(mesh);
    }

    while (agentsMesh.length > agentsData.length) {
        const mesh = agentsMesh.pop();
        scene.remove(mesh);
    }

    agentsData.forEach((agent, i) => {
        const mesh = agentsMesh[i];
        mesh.position.set(agent.x, agent.y, agent.z);

        let color = 0x00ffff; // Neutral Cyan
        if (agent.profile === 'Offensive') color = 0x00ff00; // Lime
        if (agent.profile === 'Defensive') color = 0xdc3545; // Red

        mesh.material.color.setHex(color);
    });
}

function updateObstacles3D(obstaclesData) {
    if (obstaclesMesh.length === 0 && obstaclesData.length > 0) {
        obstaclesData.forEach(obs => {
            const geometry = new THREE.BoxGeometry(obs.w, obs.w, obs.h);
            const material = new THREE.MeshPhongMaterial({
                color: 0x800000,
                transparent: true,
                opacity: 0.7,
                emissive: 0x400000
            });
            const mesh = new THREE.Mesh(geometry, material);
            mesh.position.set(obs.x, obs.y, obs.z + obs.h / 2);
            scene.add(mesh);
            obstaclesMesh.push(mesh);
        });
    }
}

function updateMap2D(exploredGrid, threatMap, agents, obstacles) {
    const width = mapCanvas.width;
    const height = mapCanvas.height;
    const res = envDimensions.resolution;

    const cellW = width / res;
    const cellH = height / res;

    // Clear with transparent background to show animated background behind
    mapCtx.clearRect(0, 0, width, height);

    for (let y = 0; y < res; y++) {
        for (let x = 0; x < res; x++) {
            const isExplored = exploredGrid[y][x];
            const threat = threatMap[y][x];

            if (isExplored) {
                let r = 0, g = 0, b = 0;

                if (threat < 0.25) {
                    // Low threat: Red (was blue)
                    const t = threat * 4;
                    r = 255; g = (1 - t) * 80; b = (1 - t) * 80;
                } else if (threat < 0.5) {
                    // Medium-low threat: Darker red (was yellow/orange)
                    const t = (threat - 0.25) * 4;
                    r = 255 - t * 60; g = 0; b = 0;
                } else if (threat < 1.0) {
                    // Medium-high threat: Even darker red (was orange/red)
                    const t = (threat - 0.5) * 2;
                    r = 195 - t * 60; g = 0; b = 0;
                } else {
                    // Very high threat: Dark grey to Black (was purple)
                    const t = Math.min(threat - 1.0, 1.0);
                    const gray = 80 * (1 - t);
                    r = gray; g = gray; b = gray;
                }

                mapCtx.fillStyle = `rgb(${r},${g},${b})`;
                mapCtx.fillRect(x * cellW, height - (y + 1) * cellH, cellW, cellH);
            }
        }
    }

    // Draw obstacles with glowing borders
    obstacles.forEach(obs => {
        const cx = (obs.x / envDimensions.width) * width;
        const cy = height - (obs.y / envDimensions.height) * height;
        const cw = (obs.w / envDimensions.width) * width * 2;
        
        // Outer glow layers
        mapCtx.save();
        mapCtx.shadowColor = '#ff4444';
        mapCtx.shadowBlur = 15;
        mapCtx.strokeStyle = '#ff2222';
        mapCtx.lineWidth = 2;
        mapCtx.strokeRect(cx - cw / 2, cy - cw / 2, cw, cw);
        
        // Inner bright border
        mapCtx.shadowBlur = 8;
        mapCtx.shadowColor = '#ff6666';
        mapCtx.strokeStyle = '#ff4444';
        mapCtx.lineWidth = 1;
        mapCtx.strokeRect(cx - cw / 2, cy - cw / 2, cw, cw);
        mapCtx.restore();
    });

    // Draw agents
    agents.forEach(agent => {
        const cx = (agent.x / envDimensions.width) * width;
        const cy = height - (agent.y / envDimensions.height) * height;

        let color = '#00ffff';
        if (agent.profile === 'Offensive') color = '#00ff00';
        if (agent.profile === 'Defensive') color = '#dc3545';

        mapCtx.fillStyle = color;
        mapCtx.beginPath();
        mapCtx.arc(cx, cy, 3, 0, Math.PI * 2);
        mapCtx.fill();
    });

    // Draw nest - smaller size
    const nx = (nestPosition.x / envDimensions.width) * width;
    const ny = height - (nestPosition.y / envDimensions.height) * height;
    mapCtx.fillStyle = '#8b0000';
    mapCtx.beginPath();
    mapCtx.arc(nx, ny, Math.max(2, width * 0.015), 0, Math.PI * 2);
    mapCtx.fill();
    mapCtx.strokeStyle = '#ffffff';
    mapCtx.lineWidth = 1;
    mapCtx.stroke();

    window.lastMapData = { explored_grid: exploredGrid, threat_map: threatMap, agents, obstacles };

    drawPathfindingOverlay();
}

// 3D Path Drawing Functions
function drawPath3D(path, color, name) {
    if (pathLines3D[name]) {
        scene.remove(pathLines3D[name]);
    }

    if (path.length < 2) return;

    const points = path.map(p => new THREE.Vector3(p.x, p.y, p.z || 250));
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({ color: color, linewidth: 2 });
    const line = new THREE.Line(geometry, material);
    
    scene.add(line);
    pathLines3D[name] = line;
}

function clearPaths3D() {
    Object.keys(pathLines3D).forEach(key => {
        if (pathLines3D[key]) {
            scene.remove(pathLines3D[key]);
            pathLines3D[key] = null;
        }
    });
}

function drawManualPath3D() {
    if (manualWaypoints.length < 2) return;
    drawPath3D(manualWaypoints, 0xffff00, 'manual');
}

function clearManualPath3D() {
    if (pathLines3D.manual) {
        scene.remove(pathLines3D.manual);
        pathLines3D.manual = null;
    }
}

// Pathfinding
function handleMapClick(event) {
    const rect = mapCanvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const worldX = (x / mapCanvas.clientWidth) * envDimensions.width;
    const worldY = ((mapCanvas.clientHeight - y) / mapCanvas.clientHeight) * envDimensions.height;

    if (!startPoint) {
        startPoint = { x: worldX, y: worldY };
        redrawMap();
    } else if (!goalPoint) {
        goalPoint = { x: worldX, y: worldY };
        findPath();
    } else {
        // Reset
        startPoint = { x: worldX, y: worldY };
        goalPoint = null;
        dijkstraPath = [];
        astarPath = [];
        safetyPath = [];
        balancedPath = [];
        clearPaths3D();
        redrawMap();
    }
}

async function findPath() {
    try {
        const response = await fetch('/pathfinding', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start: startPoint, goal: goalPoint })
        });

        const data = await response.json();

        if (data.error) {
            console.error('Pathfinding error:', data.error);
            return;
        }

        dijkstraPath = data.dijkstra.path;
        astarPath = data.astar.path;
        safetyPath = data.safety_first.path;
        balancedPath = data.balanced.path;

        // Draw paths in 3D
        drawPath3D(dijkstraPath, 0x00ff00, 'dijkstra');
        drawPath3D(astarPath, 0xff00ff, 'astar');
        drawPath3D(safetyPath, 0x00ffff, 'safety');
        drawPath3D(balancedPath, 0xffa500, 'balanced');

        pathLegend.classList.add('visible');
        redrawMap();

    } catch (error) {
        console.error('Pathfinding error:', error);
    }
}

function drawPathfindingOverlay() {
    if (!mapCtx) return;

    const width = mapCanvas.clientWidth;
    const height = mapCanvas.clientHeight;

    // Draw paths on 2D map
    const drawPath2D = (path, color) => {
        if (path.length < 2) return;
        mapCtx.strokeStyle = color;
        mapCtx.lineWidth = 2;
        mapCtx.beginPath();
        
        path.forEach((point, i) => {
            const cx = (point.x / envDimensions.width) * width;
            const cy = height - (point.y / envDimensions.height) * height;
            if (i === 0) mapCtx.moveTo(cx, cy);
            else mapCtx.lineTo(cx, cy);
        });
        
        mapCtx.stroke();
    };

    drawPath2D(dijkstraPath, '#00ff00');
    drawPath2D(astarPath, '#ff00ff');
    drawPath2D(safetyPath, '#00ffff');
    drawPath2D(balancedPath, '#ffa500');

    // Draw start/goal points
    if (startPoint) {
        const sx = (startPoint.x / envDimensions.width) * width;
        const sy = height - (startPoint.y / envDimensions.height) * height;
        mapCtx.fillStyle = '#00ff00';
        mapCtx.beginPath();
        mapCtx.arc(sx, sy, 6, 0, Math.PI * 2);
        mapCtx.fill();
        mapCtx.fillStyle = 'white';
        mapCtx.font = '10px Orbitron';
        mapCtx.textAlign = 'center';
        mapCtx.fillText('S', sx, sy - 10);
    }

    if (goalPoint) {
        const gx = (goalPoint.x / envDimensions.width) * width;
        const gy = height - (goalPoint.y / envDimensions.height) * height;
        mapCtx.fillStyle = '#dc3545';
        mapCtx.beginPath();
        mapCtx.arc(gx, gy, 6, 0, Math.PI * 2);
        mapCtx.fill();
        mapCtx.fillStyle = 'white';
        mapCtx.font = '10px Orbitron';
        mapCtx.textAlign = 'center';
        mapCtx.fillText('G', gx, gy - 10);
    }
}

function redrawMap() {
    if (window.lastMapData) {
        updateMap2D(
            window.lastMapData.explored_grid,
            window.lastMapData.threat_map,
            window.lastMapData.agents,
            window.lastMapData.obstacles
        );
    }
}

function updateFitnessStats() {
    fitnessUpdateCounter++;
    if (fitnessUpdateCounter < 10) return;
    fitnessUpdateCounter = 0;

    fetch('/fitness_statistics')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                const swarmMetrics = data.swarm_metrics;
                statFitness.textContent = swarmMetrics.avg_fitness.toFixed(2);
                
                const totalViolations = 
                    swarmMetrics.total_violations.formation +
                    swarmMetrics.total_violations.threat +
                    swarmMetrics.total_violations.time;
                statViolations.textContent = totalViolations;
            }
        })
        .catch(() => {});
}
