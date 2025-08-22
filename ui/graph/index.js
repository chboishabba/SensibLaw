let reduced = true;

async function fetchGraph(seed, hops = 1) {
  const res = await fetch(
    `/subgraph?seed=${encodeURIComponent(seed)}&hops=${hops}&reduced=${reduced}`
  );
  return res.json();
}

export async function loadGraph(seed, hops) {
  const data = await fetchGraph(seed, hops);
  renderGraph(data); // assume global renderer
}

export function toggleReduction(seed, hops) {
  reduced = !reduced;
  return loadGraph(seed, hops);
}
