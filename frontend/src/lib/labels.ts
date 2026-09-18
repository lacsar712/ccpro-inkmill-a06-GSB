import type { MatchResult, MillStatus } from './types';

export const millStatusLabel: Record<MillStatus, string> = {
  grinding: '研磨中',
  idle: '待机',
  wash: '清洗',
};

export const matchResultLabel: Record<MatchResult, string> = {
  pass: '合格',
  fail: '不合格',
};
