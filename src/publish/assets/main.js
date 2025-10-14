const viewControls = document.getElementById("view-controls");
const viewContainer = document.getElementById("view-container");
const modeButtons = new Map();
let graphData = { nodes: [], edges: [] };

if (viewContainer) {
  viewContainer.textContent = "Loading graph…";
}

function createEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) {
    el.className = className;
  }
  if (text !== undefined && text !== null) {
    el.textContent = String(text);
  }
  return el;
}

function formatLabel(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^./, (ch) => ch.toUpperCase());
}

function formatValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    const parts = value
      .map((item) => {
        if (item === null || item === undefined) {
          return "";
        }
        if (typeof item === "string" || typeof item === "number") {
          return String(item);
        }
        if (typeof item === "boolean") {
          return item ? "Yes" : "No";
        }
        return "";
      })
      .filter(Boolean);
    return parts.join(", ");
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "object") {
    return "";
  }
  return String(value);
}

function buildMetaList(metadata, excludeKeys, className) {
  if (!metadata) {
    return null;
  }
  const entries = Object.entries(metadata)
    .filter(([key]) => !excludeKeys.includes(key))
    .map(([key, value]) => [formatLabel(key), formatValue(value)])
    .filter(([, value]) => value !== "");

  if (!entries.length) {
    return null;
  }

  const list = createEl("dl", className || "meta-list");
  entries.forEach(([label, value]) => {
    list.appendChild(createEl("dt", null, label));
    list.appendChild(createEl("dd", null, value));
  });
  return list;
}

function renderCaseCard(role, node, fallbackId) {
  const card = createEl("article", "case-card");
  card.setAttribute("data-role", role.toLowerCase());
  card.appendChild(createEl("span", "case-role", role));

  if (!node) {
    card.appendChild(
      createEl(
        "p",
        "case-missing",
        `Node '${fallbackId}' is not present in this graph pack.`
      )
    );
    return card;
  }

  const typeLabel = node.type ? formatLabel(node.type) : "";
  if (typeLabel) {
    card.appendChild(createEl("span", "case-type", typeLabel));
  }

  const title =
    (node.metadata && (node.metadata.title || node.metadata.name)) || node.id;
  card.appendChild(createEl("h3", "case-title", title));

  if (node.metadata && node.metadata.summary) {
    card.appendChild(createEl("p", "case-summary", node.metadata.summary));
  }

  const meta = buildMetaList(node.metadata || {}, ["title", "name", "summary"], "case-meta");
  if (meta) {
    card.appendChild(meta);
  }

  return card;
}

function renderMirrorView(graph) {
  if (!viewContainer) {
    return;
  }

  viewContainer.innerHTML = "";
  const edges = Array.isArray(graph.edges) ? graph.edges : [];
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];

  if (!edges.length) {
    viewContainer.appendChild(
      createEl("p", "empty-state", "No issues are available for this graph yet.")
    );
    return;
  }

  const nodesById = new Map();
  nodes.forEach((node) => {
    nodesById.set(node.id, node);
  });

  edges.forEach((edge, index) => {
    const issueRow = createEl("section", "issue-row");

    const header = createEl("header", "issue-header");
    const headerTop = createEl("div", "issue-header-top");
    headerTop.appendChild(createEl("span", "issue-index", `Issue ${index + 1}`));
    const typeLabel = formatLabel(edge.type || "Relation");
    headerTop.appendChild(createEl("span", "issue-type", typeLabel));
    header.appendChild(headerTop);

    const headline =
      (edge.metadata && (edge.metadata.title || edge.metadata.label)) ||
      `${typeLabel} between ${edge.source} and ${edge.target}`;
    header.appendChild(createEl("h2", "issue-title", headline));

    if (edge.metadata && edge.metadata.summary) {
      header.appendChild(createEl("p", "issue-summary", edge.metadata.summary));
    }

    const edgeMetaSource = {
      ...((edge.metadata && typeof edge.metadata === "object" && edge.metadata) || {}),
    };
    if (edge.weight !== undefined && edge.weight !== null) {
      edgeMetaSource.weight = edge.weight;
    }
    const edgeMeta = buildMetaList(edgeMetaSource, ["title", "label", "summary"], "issue-meta");
    if (edgeMeta) {
      header.appendChild(edgeMeta);
    }

    issueRow.appendChild(header);

    const cards = createEl("div", "issue-cards");
    cards.appendChild(renderCaseCard("Source", nodesById.get(edge.source), edge.source));
    cards.appendChild(renderCaseCard("Target", nodesById.get(edge.target), edge.target));
    issueRow.appendChild(cards);

    viewContainer.appendChild(issueRow);
  });
}

const viewModes = [
  {
    id: "mirror",
    label: "Mirror view",
    description: "Compare linked matters in paired cards.",
    render: renderMirrorView,
  },
];

function setActiveMode(modeId) {
  const mode = viewModes.find((item) => item.id === modeId);
  if (!mode) {
    return;
  }
  mode.render(graphData);
  modeButtons.forEach((btn, key) => {
    btn.setAttribute("aria-pressed", key === modeId ? "true" : "false");
  });
}

function buildControls() {
  if (!viewControls) {
    return;
  }
  viewControls.innerHTML = "";
  modeButtons.clear();
  viewModes.forEach((mode) => {
    const button = createEl("button", "view-button", mode.label);
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    if (mode.description) {
      button.setAttribute("title", mode.description);
    }
    button.addEventListener("click", () => setActiveMode(mode.id));
    viewControls.appendChild(button);
    modeButtons.set(mode.id, button);
  });
}

function normaliseGraph(raw) {
  const nodes = raw && Array.isArray(raw.nodes) ? raw.nodes : [];
  const edges = raw && Array.isArray(raw.edges) ? raw.edges : [];
  return { nodes, edges };
}

function handleError(message) {
  if (viewControls) {
    viewControls.innerHTML = "";
  }
  if (viewContainer) {
    viewContainer.innerHTML = "";
    viewContainer.appendChild(createEl("p", "empty-state", message));
  }
}

fetch("graph.json")
  .then((resp) => {
    if (!resp.ok) {
      throw new Error("Graph request failed");
    }
    return resp.json();
  })
  .then((data) => {
    graphData = normaliseGraph(data);
    buildControls();
    if (viewModes.length) {
      setActiveMode(viewModes[0].id);
    } else if (viewContainer) {
      viewContainer.innerHTML = "";
    }
  })
  .catch(() => {
    handleError("Unable to load graph data.");
  });
