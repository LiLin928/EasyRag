# Changelog

All notable changes to the EasyRAG project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added

#### Workflow Editor Improvements (2026-09-16)

**RAG Node Configuration Enhancements:**
- Real knowledge base selection from system (replaces hardcoded mock data)
- Embedding model selection with default model indicator
- Output variable presets for RAG nodes (5 preset options)
- Quick selection buttons for output variables
- Field descriptions in dropdown options
- Node preview displays selected knowledge bases and models

**LLM Node Improvements:**
- Model selection from system settings
- Output variable presets (content, tokens, model, etc.)
- Default model indicator in dropdown

**Workflow Editor Fixes:**
- Fixed drag-and-drop node creation (consistent data transfer keys)
- Fixed new workflow save functionality (auto-create before save)
- Fixed workflow publishing for new workflows
- Fixed workflow execution for new workflows

---

## Release Notes

### Workflow Editor - 2026-09-16

This release brings significant improvements to the workflow editor, focusing on RAG and LLM node configuration.

#### RAG Node Configuration

**Before:**
- Knowledge base selection used hardcoded mock data (`kb-1`, `kb-2`)
- No Embedding model selection
- Manual input required for output variable paths

**After:**
- ✅ Real knowledge bases from system with document counts
- ✅ Embedding model selection with default indicators
- ✅ 5 preset output variables with quick selection
- ✅ Clear field descriptions in dropdowns

#### LLM Node Configuration

**Improvements:**
- ✅ Models loaded from system settings
- ✅ Output variable presets
- ✅ Better UX with quick selection buttons

#### Workflow Editor Core Fixes

**Fixed Issues:**
1. **Drag-and-Drop:** Nodes now appear on canvas when dragged from palette
2. **New Workflow Save:** "Save" button now creates workflow before saving
3. **Publishing:** New workflows can be published directly
4. **Execution:** New workflows can be executed without manual save first

#### Technical Changes

**New Dependencies:**
- `useKnowledgeStore` for knowledge base integration
- `useSettingsStore` for model configuration

**Modified Files:**
- `frontend/src/views/workflow/components/NodeConfigModal.vue`
- `frontend/src/views/workflow/WorkflowEditorView.vue`
- `frontend/src/views/workflow/components/WorkflowCanvas.vue`
- `frontend/src/stores/workflow.ts`
- `frontend/src/mock/workflow.ts`

**New Computed Properties:**
- `enabledKnowledgeBases` - Filtered list of enabled knowledge bases
- `enabledEmbedModels` - Filtered list of enabled embedding models
- `ragOutputPresets` - RAG output variable presets
- `isRAGOutputDef` - RAG node output definition flag
- `llmOutputPresets` - LLM output variable presets
- `isLLMOutputDef` - LLM node output definition flag

**New Methods:**
- `create()` - Create new workflow in store
- `addPresetOutput()` - Add preset output variable

---

## Migration Guide

### For Developers

No migration required. All changes are backward compatible.

### For Users

**Knowledge Base Selection:**
- Previously selected mock knowledge bases (`kb-1`, `kb-2`) will not persist
- Users need to select real knowledge bases from the system

**Embedding Model:**
- New optional field
- If not selected, system default model will be used

**Output Variables:**
- Existing manually configured output variables will remain
- New preset buttons available for quick configuration

---

## Known Issues

None. All planned improvements have been implemented and tested.

---

## Future Improvements

Based on the comprehensive node analysis (see `docs/superpowers/specs/2026-09-16-workflow-node-output-settings-analysis.md`):

**Medium Priority:**
- Template rendering node improvements
- Human intervention node improvements

**Low Priority:**
- Code execution node improvements
- HTTP request node improvements
- Condition node improvements

---

## References

- [Node Output Settings Analysis Report](docs/superpowers/specs/2026-09-16-workflow-node-output-settings-analysis.md)
- [RAG Node Improvements Design](docs/superpowers/specs/2026-09-16-rag-node-config-improvements-design.md)
- [Implementation Plan](docs/superpowers/plans/2026-09-16-rag-node-config-improvements.md)
- [Test Guide](test-report-rag-node.md)