# Backend Notes

## Theming is frontend-only
This project does not persist or serve any `custom_css` from the backend. All design and theming are handled client-side in the frontend templates/components.

- The `Proposal` schema and model no longer include `custom_css`.
- No endpoints accept or return `custom_css`.

If your local database was created from an older branch that included a `custom_css` column, you can either:
- Ignore the extra column (unused by the app), or
- Drop it via migration. If Alembic is added later, a migration can be provided to remove the column.

## API Summary
- Proposals: create, get, update
- Sections: create, update, reorder, delete
- AI: content enhancement, chart generation (via agents)
- Images: user image library (URLs) and attach to sections

See `app/api/v1/endpoints` for details.
