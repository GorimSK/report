// Asana webhook events -> unique task gids whose "completed" field changed.
const gids = new Set();
for (const { json: e } of $input.all()) {
  const events = Array.isArray(e.events) ? e.events : [e];
  for (const ev of events) {
    if (ev && ev.resource && ev.resource.resource_type === 'task'
        && ev.action === 'changed' && ev.change && ev.change.field === 'completed') {
      gids.add(String(ev.resource.gid));
    }
  }
}
return [...gids].map((gid) => ({ json: { task_gid: gid } }));
