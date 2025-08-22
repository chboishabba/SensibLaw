fetch('graph.json')
  .then(resp => resp.json())
  .then(data => {
    const list = document.getElementById('node-list');
    (data.nodes || []).forEach(n => {
      const li = document.createElement('li');
      const title = n.metadata && n.metadata.title ? ' - ' + n.metadata.title : '';
      li.textContent = n.id + title;
      list.appendChild(li);
    });
  });
