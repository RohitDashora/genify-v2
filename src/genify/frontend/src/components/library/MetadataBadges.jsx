import { templateLabel } from './metadataLabels'

export default function MetadataBadges({ templateType, isCombined }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-border-subtle bg-gray-100 text-gray-700">
        {templateLabel(templateType)}
      </span>
      {isCombined && (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-blue-200 bg-blue-50 text-blue-800">
          Combined
        </span>
      )}
    </div>
  )
}
