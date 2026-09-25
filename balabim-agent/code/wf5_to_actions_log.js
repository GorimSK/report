// Asana task detail -> actions_log row, only for tasks that are now completed.
const logged = new Date().toISOString();
return $input.all()
  .map((i) => i.json.data || i.json)
  .filter((t) => t && t.completed)
  .map((t) => ({
    json: {
      task_gid: String(t.gid),
      completed_at: t.completed_at,
      completed_by: (t.completed_by && t.completed_by.name) || '',
      task_name: t.name || '',
      logged_at: logged,
    },
  }));
