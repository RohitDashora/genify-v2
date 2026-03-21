import { useState } from 'react'
import CatalogBrowser from './CatalogBrowser'
import SessionLauncher from './SessionLauncher'
import SessionList from './SessionList'
import HelpHint from './HelpHint'

export default function Home() {
  const [selectedTables, setSelectedTables] = useState([])
  const [catalog, setCatalog] = useState('')
  const [schema, setSchema] = useState('')

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <p className="text-sm text-gray-600 max-w-2xl">
          Select tables from Unity Catalog, choose a template, then start a session.
        </p>
        <HelpHint label="About Genify">
          Genify generates structured metadata (YAML) for your tables using AI agents and MCP tools. Choose tables, pick a template, and let the agent fill in the sections.
        </HelpHint>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-w-0">
        <div className="lg:col-span-2 space-y-6">
          <CatalogBrowser
            onSelect={(tables, cat, sch) => {
              setSelectedTables(tables)
              setCatalog(cat)
              setSchema(sch)
            }}
          />
          <SessionLauncher
            selectedTables={selectedTables}
            catalog={catalog}
            schema={schema}
          />
        </div>
        <div>
          <SessionList />
        </div>
      </div>
    </div>
  )
}
