export async function repairListActions(params: { root_path: string; ticket_id?: number }) {
  return http.get("/wp-repair/actions", { params }).then(r => r.data);
}
