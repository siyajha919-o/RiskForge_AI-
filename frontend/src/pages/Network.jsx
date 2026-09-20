import { useEffect, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

import { api } from '../lib/api';
import { CHART, num, riskStyle } from '../lib/format';
import { EmptyState, ErrorState, Loading, Panel, SectionHeading, StatCard } from '../components/ui';

/** Radial layout: business units at centre, their assets around them, each
 *  asset's vulnerabilities orbiting it. Deterministic per node id, so the
 *  graph doesn't reshuffle on every re-render. */
function layout(nodes, edges) {
  const byType = { business_unit: [], asset: [], vulnerability: [] };
  nodes.forEach((n) => byType[n.type]?.push(n));

  const positions = new Map();
  byType.business_unit.forEach((n, i) => {
    const a = (i / Math.max(1, byType.business_unit.length)) * Math.PI * 2;
    positions.set(n.id, new THREE.Vector3(Math.cos(a) * 4, Math.sin(a) * 4, 0));
  });

  const childrenOf = new Map();
  edges.forEach((e) => {
    if (!childrenOf.has(e.source)) childrenOf.set(e.source, []);
    childrenOf.get(e.source).push(e.target);
  });

  byType.asset.forEach((n) => {
    const parentEdge = edges.find((e) => e.target === n.id && e.kind === 'owns');
    const parent = parentEdge ? positions.get(parentEdge.source) : null;
    const base = parent || new THREE.Vector3(0, 0, 0);
    const hash = [...n.id].reduce((a, c) => a + c.charCodeAt(0), 0);
    const a = (hash % 360) * (Math.PI / 180);
    const r = 2.2 + (hash % 5) * 0.3;
    positions.set(
      n.id,
      base.clone().add(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, (hash % 7) - 3))
    );
  });

  byType.vulnerability.forEach((n) => {
    const parentEdge = edges.find((e) => e.source === n.id && e.kind === 'exposes');
    const parent = parentEdge ? positions.get(parentEdge.target) : null;
    const base = parent || new THREE.Vector3(0, 0, 0);
    const hash = [...n.id].reduce((a, c) => a + c.charCodeAt(0), 0);
    const a = (hash % 360) * (Math.PI / 180);
    positions.set(n.id, base.clone().add(new THREE.Vector3(Math.cos(a) * 0.9, Math.sin(a) * 0.9, 0.6)));
  });

  return positions;
}

function Node({ position, size, color, onClick }) {
  return (
    <mesh position={position} onClick={onClick}>
      <sphereGeometry args={[size, 16, 16]} />
      <meshBasicMaterial color={color} toneMapped={false} />
    </mesh>
  );
}

function Scene({ nodes, edges, onSelect }) {
  const positions = useMemo(() => layout(nodes, edges), [nodes, edges]);

  const sizeFor = { business_unit: 0.32, asset: 0.16, vulnerability: 0.07 };
  const colorFor = (n) => riskStyle(n.risk_level).hex;

  return (
    <>
      <ambientLight intensity={0.9} />
      {edges.map((e, i) => {
        const a = positions.get(e.source);
        const b = positions.get(e.target);
        if (!a || !b) return null;
        return (
          <line key={i}>
            <bufferGeometry>
              <bufferAttribute
                attach="attributes-position"
                count={2}
                array={new Float32Array([a.x, a.y, a.z, b.x, b.y, b.z])}
                itemSize={3}
              />
            </bufferGeometry>
            <lineBasicMaterial color={CHART.sand} transparent opacity={0.22} />
          </line>
        );
      })}
      {nodes.map((n) => {
        const p = positions.get(n.id);
        if (!p) return null;
        return (
          <Node
            key={n.id}
            position={p}
            size={sizeFor[n.type] || 0.1}
            color={colorFor(n)}
            onClick={() => onSelect(n)}
          />
        );
      })}
      <OrbitControls enablePan={false} minDistance={3} maxDistance={20} autoRotate autoRotateSpeed={0.4} />
    </>
  );
}

export default function Network() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const load = () => {
    setError(null);
    api.network(150).then(setData).catch((e) => setError(e.friendlyMessage));
  };
  useEffect(() => { load(); }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading label="Building asset graph…" />;

  return (
    <>
      <SectionHeading
        title="Cyber risk network"
        subtitle="Business units, assets and the vulnerabilities exposing them"
      />

      {/* The first three count what is drawn, not what exists: the API caps the
          subgraph so the canvas stays interactive, so these must say so or they
          read as estate totals and contradict the dashboard. Attack paths is a
          genuine total from the Bayesian graph, so it carries no qualifier. */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Assets" value={num(data.stats.assets)} sub="Highest-risk subset, graphed" />
        <StatCard label="Vulnerabilities" value={num(data.stats.vulnerabilities)} sub="Exposing the graphed assets" />
        <StatCard label="Connections" value={num(data.stats.edges)} sub="Edges in this subgraph" />
        <StatCard label="Attack paths found" value={num(data.stats.attack_paths)} sub="Total across the estate" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2 !p-0 overflow-hidden" title={null}>
          {!data.nodes.length ? (
            <EmptyState message="No graph data available." hint="Run the pipeline to generate asset and vulnerability data." />
          ) : (
            <div className="h-[520px]">
              <Canvas camera={{ position: [0, 0, 12], fov: 55 }}>
                <color attach="background" args={[CHART.ink]} />
                <Scene nodes={data.nodes} edges={data.edges} onSelect={setSelected} />
              </Canvas>
            </div>
          )}
        </Panel>

        <Panel title="Legend & selection" subtitle="Click a node to inspect it">
          <div className="mb-4 space-y-2 text-xs">
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-cream" /> Business unit (large)</div>
            <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-smoke" /> Asset (medium)</div>
            <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-risk-critical" /> Vulnerability (small)</div>
            <p className="pt-1 text-muted">Colour follows risk level: green → red.</p>
          </div>

          {selected ? (
            <div className="rounded-lg border border-sand/20 bg-slate/50 p-3">
              <p className="text-xs uppercase tracking-wider text-muted">{selected.type.replace('_', ' ')}</p>
              <p className="mt-1 truncate text-sm font-semibold text-cream">{selected.label}</p>
              <p className="mt-2 text-xs text-muted">Risk level: <span className="text-cream">{selected.risk_level}</span></p>
              {selected.criticality != null && (
                <p className="text-xs text-muted">Criticality: <span className="text-cream">{selected.criticality}</span></p>
              )}
              {selected.expected_annual_loss > 0 && (
                <p className="text-xs text-muted">
                  Modelled EAL: <span className="text-cream">₹{selected.expected_annual_loss.toLocaleString('en-IN')}</span>
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted">No node selected.</p>
          )}
        </Panel>
      </div>
    </>
  );
}
