/** In-app route for a record: employees open their profile, everything else the record view. */
export function recordPath(doctype: string, name: string) {
  return doctype === 'Employee' ? `/people/${encodeURIComponent(name)}` : `/r/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`
}
