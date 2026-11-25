/* Read-only playback of existing algorithm output streams. */
(function (root) {
  'use strict';
  root.AiMonitorAnalysisPreview = root.AiMonitorPreviewFactory({
    name: 'AnalysisPreview',
    layouts: [1, 4, 9, 16, 25],
    apiPrefix: '/video_view/analysis_preview/',
    className: 'analysis-preview',
    heading: '分析监控点',
    windowLabel: '分析窗口',
    layoutLabel: '分析分屏',
    liveLabel: '分析流',
    searchPlaceholder: '搜索监控点、任务或算法',
    emptySources: '暂无已关联算法输出流的监控点',
    mediaStatusUnknownHint: '暂时无法确认分析推流状态，请刷新重试',
    showTasks: true,
    selectionHint: '选择监控点播放已有分析流；勾选多路后点击播放所选。',
    bottomHint: '双击窗口放大 / 还原 · 视频默认静音 · 停止仅关闭播放窗口，算法任务继续运行',
    temporaryAnalysisRoute: null, // Set '/spfx_test' to restore the temporary entry.
  });
})(window);
