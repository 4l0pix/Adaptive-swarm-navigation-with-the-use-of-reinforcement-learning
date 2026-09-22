import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const GRID_DIVISIONS = 25;
const COLORS = {
    background: 0x0c0d0c,
    signal: 0x8e54de,
    ink0: 0xf0f0ec,
    ink3: 0x85857f,
    ink5: 0x41413d,
    ink6: 0x232321,
};

function fail(path, expectation) {
    throw new TypeError(`EnvironmentView: ${path} ${expectation}`);
}

function requireObject(value, path) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        fail(path, 'must be an object');
    }
}

function requireNumber(value, path, { positive = false } = {}) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        fail(path, 'must be a finite number');
    }
    if (positive && value <= 0) fail(path, 'must be greater than zero');
}

function requireId(value, path) {
    if ((typeof value !== 'string' && typeof value !== 'number') || value === '') {
        fail(path, 'must be a non-empty string or number');
    }
}

function requirePosition(value, path) {
    requireObject(value, path);
    for (const axis of ['x', 'y', 'z']) requireNumber(value[axis], `${path}.${axis}`);
}

function requireUniqueIds(items, path) {
    const ids = new Set();
    items.forEach((item, index) => {
        requireObject(item, `${path}[${index}]`);
        requireId(item.id, `${path}[${index}].id`);
        const key = String(item.id);
        if (ids.has(key)) fail(`${path}[${index}].id`, `duplicates ${JSON.stringify(item.id)}`);
        ids.add(key);
    });
}

export function validateEnvironmentWorld(world) {
    requireObject(world, 'world');
    requireNumber(world.size, 'world.size', { positive: true });
    requirePosition(world.nest, 'world.nest');
    if (!Array.isArray(world.agents)) fail('world.agents', 'must be an array');
    if (!Array.isArray(world.obstacles)) fail('world.obstacles', 'must be an array');
    requireUniqueIds(world.agents, 'world.agents');
    requireUniqueIds(world.obstacles, 'world.obstacles');

    world.agents.forEach((agent, index) => {
        requireObject(agent, `world.agents[${index}]`);
        requirePosition(agent, `world.agents[${index}]`);
        if (typeof agent.profile !== 'string' || !agent.profile.trim()) {
            fail(`world.agents[${index}].profile`, 'must be a non-empty string');
        }
    });
    world.obstacles.forEach((obstacle, index) => {
        requireObject(obstacle, `world.obstacles[${index}]`);
        requirePosition(obstacle, `world.obstacles[${index}]`);
        requireNumber(obstacle.w, `world.obstacles[${index}].w`, { positive: true });
        requireNumber(obstacle.h, `world.obstacles[${index}].h`, { positive: true });
    });
    return world;
}

function disposeObject(object) {
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) material?.dispose();
}

function profileColor(profile) {
    const name = profile.toLowerCase();
    if (name === 'offensive') return COLORS.signal;
    if (name === 'defensive') return COLORS.ink3;
    return COLORS.ink0;
}

export class EnvironmentView {
    constructor(container, initialWorld) {
        if (!(container instanceof HTMLElement)) {
            fail('container', 'must be an HTMLElement');
        }
        validateEnvironmentWorld(initialWorld);

        this.container = container;
        this.disposed = false;
        this.worldSize = initialWorld.size;
        this.agentMeshes = new Map();
        this.obstacleMeshes = new Map();
        this.pathLines = new Map();
        this.explorationGridData = null;
        this.explorationInstancedMesh = null;
        this.explorationCellSize = 0;
        this.veilEnabled = true;
        this.tempMatrix = new THREE.Matrix4();
        this.zeroScale = new THREE.Matrix4().makeScale(0, 0, 0);
        this.resize = this.resize.bind(this);

        this.container.classList.add('environment-view');
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(COLORS.background);
        this.camera = new THREE.PerspectiveCamera(60, 1, 0.1, this.worldSize * 4);
        this.camera.up.set(0, 0, 1);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        this.container.appendChild(this.renderer.domElement);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;

        this.dynamicGroup = new THREE.Group();
        this.pathGroup = new THREE.Group();
        this.scene.add(this.dynamicGroup, this.pathGroup);
        this.mountControls();
        this.buildWorld(initialWorld.size);
        this.createNestMesh();
        this.update(initialWorld);
        this.resize();

        this.resizeObserver = typeof ResizeObserver === 'undefined'
            ? null
            : new ResizeObserver(this.resize);
        this.resizeObserver?.observe(this.container);
        window.addEventListener('resize', this.resize);
        this.renderer.setAnimationLoop(() => {
            this.controls.update();
            this.renderer.render(this.scene, this.camera);
        });
    }

    assertActive() {
        if (this.disposed) throw new Error('EnvironmentView: instance has been disposed');
    }

    mountControls() {
        this.toolbar = document.createElement('div');
        this.toolbar.className = 'environment-view__controls';
        this.toolbar.setAttribute('aria-label', 'Environment view controls');

        this.veilButton = this.makeButton('Toggle Veil', 'Toggle exploration veil', () => {
            this.toggleVeil();
        }, 'environment-view__control--veil');
        this.veilButton.setAttribute('aria-pressed', 'true');
        this.toolbar.append(
            this.veilButton,
            this.makeButton('+', 'Zoom in', () => this.zoomIn()),
            this.makeButton('\u2212', 'Zoom out', () => this.zoomOut()),
            this.makeButton('\u2302', 'Reset view', () => this.resetView()),
        );
        this.container.appendChild(this.toolbar);
    }

    makeButton(label, accessibleName, handler, modifier = '') {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `environment-view__control ${modifier}`.trim();
        button.textContent = label;
        button.title = accessibleName;
        button.setAttribute('aria-label', accessibleName);
        button.addEventListener('click', handler);
        return button;
    }

    buildWorld(size) {
        if (this.staticGroup) {
            this.scene.remove(this.staticGroup);
            this.staticGroup.traverse(disposeObject);
        }
        if (this.explorationInstancedMesh) {
            this.scene.remove(this.explorationInstancedMesh);
            disposeObject(this.explorationInstancedMesh);
        }

        this.worldSize = size;
        this.camera.far = size * 4;
        this.camera.updateProjectionMatrix();
        this.controls.minDistance = size * 0.2;
        this.controls.maxDistance = size * 3;

        this.staticGroup = new THREE.Group();
        this.scene.add(this.staticGroup);
        this.staticGroup.add(new THREE.AmbientLight(0x404040, 0.6));
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(size * 0.6, size * 0.6, size * 0.8);
        this.staticGroup.add(directionalLight);
        const signalLight = new THREE.PointLight(COLORS.signal, 0.35, size * 1.6);
        signalLight.position.set(size / 2, size / 2, size * 1.2);
        this.staticGroup.add(signalLight);

        const grid = new THREE.GridHelper(size, GRID_DIVISIONS, COLORS.ink5, COLORS.ink6);
        grid.rotation.x = Math.PI / 2;
        grid.position.set(size / 2, size / 2, 0);
        this.staticGroup.add(grid);

        const boundaryGeometry = new THREE.BoxGeometry(size, size, size);
        const boundaryEdges = new THREE.EdgesGeometry(boundaryGeometry);
        boundaryGeometry.dispose();
        const boundary = new THREE.LineSegments(
            boundaryEdges,
            new THREE.LineBasicMaterial({ color: COLORS.signal, opacity: 0.42, transparent: true }),
        );
        boundary.position.set(size / 2, size / 2, size / 2);
        this.staticGroup.add(boundary);
        this.staticGroup.add(new THREE.AxesHelper(size * 0.1));

        this.initExplorationGrid();
        this.resetView();
    }

    createNestMesh() {
        const geometry = new THREE.ConeGeometry(6, 12, 6);
        const material = new THREE.MeshPhongMaterial({
            color: COLORS.signal,
            emissive: COLORS.ink6,
            shininess: 24,
        });
        this.nestMesh = new THREE.Mesh(geometry, material);
        this.nestMesh.rotation.x = Math.PI;
        this.dynamicGroup.add(this.nestMesh);
    }

    initExplorationGrid() {
        this.explorationGridData = new Uint8Array(GRID_DIVISIONS ** 3);
        this.explorationCellSize = this.worldSize / GRID_DIVISIONS;
        const geometry = new THREE.BoxGeometry(
            this.explorationCellSize,
            this.explorationCellSize,
            this.explorationCellSize,
        );
        const material = new THREE.MeshBasicMaterial({ color: 0x000000, depthWrite: true });
        this.explorationInstancedMesh = new THREE.InstancedMesh(
            geometry,
            material,
            GRID_DIVISIONS ** 3,
        );
        this.explorationInstancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        let index = 0;
        for (let x = 0; x < GRID_DIVISIONS; x += 1) {
            for (let y = 0; y < GRID_DIVISIONS; y += 1) {
                for (let z = 0; z < GRID_DIVISIONS; z += 1) {
                    this.tempMatrix.makeTranslation(
                        x * this.explorationCellSize + this.explorationCellSize / 2,
                        y * this.explorationCellSize + this.explorationCellSize / 2,
                        z * this.explorationCellSize + this.explorationCellSize / 2,
                    );
                    this.explorationInstancedMesh.setMatrixAt(index, this.tempMatrix);
                    index += 1;
                }
            }
        }
        this.explorationInstancedMesh.visible = this.veilEnabled;
        this.explorationInstancedMesh.instanceMatrix.needsUpdate = true;
        this.scene.add(this.explorationInstancedMesh);
    }

    updateExploration(agents) {
        const cellSize = this.explorationCellSize;
        const visualRange = this.worldSize * 0.06;
        const rangeInCells = Math.ceil(visualRange / cellSize);
        let changed = false;
        for (const agent of agents) {
            const origin = [agent.x, agent.y, agent.z].map((value) => Math.floor(value / cellSize));
            for (let dx = -rangeInCells; dx <= rangeInCells; dx += 1) {
                for (let dy = -rangeInCells; dy <= rangeInCells; dy += 1) {
                    for (let dz = -rangeInCells; dz <= rangeInCells; dz += 1) {
                        const [x, y, z] = [origin[0] + dx, origin[1] + dy, origin[2] + dz];
                        if ([x, y, z].some((value) => value < 0 || value >= GRID_DIVISIONS)) continue;
                        if (Math.hypot(dx, dy, dz) * cellSize > visualRange) continue;
                        const index = x * GRID_DIVISIONS ** 2 + y * GRID_DIVISIONS + z;
                        if (this.explorationGridData[index]) continue;
                        this.explorationGridData[index] = 1;
                        this.explorationInstancedMesh.setMatrixAt(index, this.zeroScale);
                        changed = true;
                    }
                }
            }
        }
        if (changed) this.explorationInstancedMesh.instanceMatrix.needsUpdate = true;
    }

    reconcileAgents(agents) {
        const active = new Set(agents.map((agent) => String(agent.id)));
        for (const [id, mesh] of this.agentMeshes) {
            if (active.has(id)) continue;
            this.dynamicGroup.remove(mesh);
            disposeObject(mesh);
            this.agentMeshes.delete(id);
        }
        for (const agent of agents) {
            const id = String(agent.id);
            let mesh = this.agentMeshes.get(id);
            if (!mesh) {
                mesh = new THREE.Mesh(
                    new THREE.SphereGeometry(4, 16, 16),
                    new THREE.MeshPhongMaterial({ color: COLORS.ink0 }),
                );
                this.dynamicGroup.add(mesh);
                this.agentMeshes.set(id, mesh);
            }
            mesh.position.set(agent.x, agent.y, agent.z);
            mesh.material.color.setHex(profileColor(agent.profile));
        }
    }

    reconcileObstacles(obstacles) {
        const active = new Set(obstacles.map((obstacle) => String(obstacle.id)));
        for (const [id, record] of this.obstacleMeshes) {
            if (active.has(id)) continue;
            this.dynamicGroup.remove(record.mesh);
            disposeObject(record.mesh);
            this.obstacleMeshes.delete(id);
        }
        for (const obstacle of obstacles) {
            const id = String(obstacle.id);
            let record = this.obstacleMeshes.get(id);
            if (!record || record.w !== obstacle.w || record.h !== obstacle.h) {
                if (record) {
                    this.dynamicGroup.remove(record.mesh);
                    disposeObject(record.mesh);
                }
                const mesh = new THREE.Mesh(
                    new THREE.BoxGeometry(obstacle.w, obstacle.w, obstacle.h),
                    new THREE.MeshPhongMaterial({
                        color: COLORS.signal,
                        transparent: true,
                        opacity: 0.62,
                        emissive: COLORS.ink6,
                    }),
                );
                this.dynamicGroup.add(mesh);
                record = { mesh, w: obstacle.w, h: obstacle.h };
                this.obstacleMeshes.set(id, record);
            }
            record.mesh.position.set(obstacle.x, obstacle.y, obstacle.z + obstacle.h / 2);
        }
    }

    update(world) {
        this.assertActive();
        validateEnvironmentWorld(world);
        if (world.size !== this.worldSize) {
            this.clearPaths();
            this.buildWorld(world.size);
        }
        this.nestMesh.position.set(world.nest.x, world.nest.y, world.nest.z);
        this.reconcileAgents(world.agents);
        this.reconcileObstacles(world.obstacles);
        this.updateExploration(world.agents);
    }

    setPath(name, points, color = '#f0f0ec') {
        this.assertActive();
        if (typeof name !== 'string' || !name) fail('path name', 'must be a non-empty string');
        if (!Array.isArray(points)) fail(`path ${name}`, 'must be an array');
        points.forEach((point, index) => {
            requireObject(point, `path ${name}[${index}]`);
            requireNumber(point.x, `path ${name}[${index}].x`);
            requireNumber(point.y, `path ${name}[${index}].y`);
            if (point.z !== undefined) requireNumber(point.z, `path ${name}[${index}].z`);
        });
        this.clearPath(name);
        if (points.length < 2) return;
        const geometry = new THREE.BufferGeometry().setFromPoints(
            points.map((point) => new THREE.Vector3(point.x, point.y, point.z ?? this.worldSize / 2)),
        );
        const line = new THREE.Line(
            geometry,
            new THREE.LineBasicMaterial({ color: new THREE.Color(color) }),
        );
        this.pathGroup.add(line);
        this.pathLines.set(name, line);
    }

    clearPath(name) {
        const line = this.pathLines.get(name);
        if (!line) return;
        this.pathGroup.remove(line);
        disposeObject(line);
        this.pathLines.delete(name);
    }

    clearPaths() {
        for (const name of [...this.pathLines.keys()]) this.clearPath(name);
    }

    getExplorationPercentage() {
        this.assertActive();
        let explored = 0;
        for (const value of this.explorationGridData) explored += value;
        return (explored / this.explorationGridData.length) * 100;
    }

    zoomIn() {
        this.assertActive();
        this.zoomBy(0.8);
    }

    zoomOut() {
        this.assertActive();
        this.zoomBy(1.25);
    }

    zoomBy(factor) {
        const distance = this.camera.position.distanceTo(this.controls.target);
        const nextDistance = THREE.MathUtils.clamp(
            distance * factor,
            this.controls.minDistance,
            this.controls.maxDistance,
        );
        const direction = this.camera.position.clone().sub(this.controls.target).normalize();
        this.camera.position.copy(this.controls.target).add(direction.multiplyScalar(nextDistance));
        this.controls.update();
    }

    resetView() {
        this.assertActive();
        const size = this.worldSize;
        this.camera.position.set(size * 1.2, size * -0.4, size);
        this.controls.target.set(size / 2, size / 2, size / 2);
        this.controls.update();
    }

    toggleVeil() {
        this.assertActive();
        this.veilEnabled = !this.veilEnabled;
        this.explorationInstancedMesh.visible = this.veilEnabled;
        this.veilButton.setAttribute('aria-pressed', String(this.veilEnabled));
        this.veilButton.title = this.veilEnabled ? 'Hide exploration veil' : 'Show exploration veil';
        return this.veilEnabled;
    }

    resize() {
        if (this.disposed) return;
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        if (!width || !height) return;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height, false);
    }

    dispose() {
        if (this.disposed) return;
        this.disposed = true;
        this.renderer.setAnimationLoop(null);
        this.resizeObserver?.disconnect();
        window.removeEventListener('resize', this.resize);
        this.controls.dispose();
        this.scene.traverse(disposeObject);
        this.renderer.dispose();
        this.renderer.forceContextLoss?.();
        this.toolbar.remove();
        this.renderer.domElement.remove();
        this.container.classList.remove('environment-view');
        this.agentMeshes.clear();
        this.obstacleMeshes.clear();
        this.pathLines.clear();
    }
}
