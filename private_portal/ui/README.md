UI dependencies: Uppy core 4.5.2, XHRUpload 4.3.3, Tabulator 6.3.1.
Run npm ci, then npm run build from this directory. Copy table CSS from node_modules/tabulator-tables/dist/css/tabulator.min.css and mirror static assets to public/static.
Views are read-only. Uploads preserve the existing API, CSRF protection and file validation. No database migration is required.
