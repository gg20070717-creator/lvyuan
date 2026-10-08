import client from './client'

export type AssetType = 'lecture' | 'practice_guide' | 'graded_quiz' | 'text' | 'plan' | 'report' | 'wrong_book'

export interface AssetItem {
  asset_id: string
  title: string
  asset_type: string
  source_tool: string
  session_id: string
  created_at: string
  content?: string
  evidence_ids?: string[]  // 结构化引用链（T14）：生成依据的知识片段
}

export interface AssetListResponse {
  total: number
  assets: AssetItem[]
}

export function listAssets(
  userId: string,
  assetType?: string,
  limit?: number,
): Promise<AssetListResponse> {
  return client.get(`/users/${userId}/assets`, {
    params: { asset_type: assetType, limit },
  }) as unknown as Promise<AssetListResponse>
}

export function getAsset(assetId: string): Promise<AssetItem> {
  return client.get(`/assets/${assetId}`) as unknown as Promise<AssetItem>
}

export function deleteAsset(assetId: string): Promise<{ status: string; asset_id: string }> {
  return client.delete(`/assets/${assetId}`) as unknown as Promise<{ status: string; asset_id: string }>
}

/** 资产类型 → 中文标签 / 颜色 / 图标名（学习中心展示用） */
export const ASSET_TYPE_META: Record<string, { label: string; color: string; emoji: string }> = {
  lecture: { label: '讲义', color: '#338FF2', emoji: '📖' },
  practice_guide: { label: '实操指南', color: '#338FF2', emoji: '🧭' },
  graded_quiz: { label: '测试', color: '#e8875b', emoji: '📝' },
  text: { label: '文档', color: '#2d8a2d', emoji: '📄' },
  plan: { label: '学习计划', color: '#7c3aed', emoji: '🗺️' },
  report: { label: '学习报告', color: '#e8875b', emoji: '📊' },
  wrong_book: { label: '易错题 降维解释', color: '#C0504D', emoji: '💡' },
}

export function assetTypeLabel(t: string): string {
  return ASSET_TYPE_META[t]?.label || t || '文档'
}

export function assetTypeEmoji(t: string): string {
  return ASSET_TYPE_META[t]?.emoji || '📄'
}
