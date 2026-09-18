"""Expanded analytics. Every primary value is exact or explicitly unavailable."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTabWidget,QTableWidget,
    QTableWidgetItem,QHeaderView,QAbstractItemView,QPlainTextEdit,QWidget,QPushButton,QApplication)

HELP = {
 'total_tokens':'Official OpenAI total where available; otherwise input + output. Cached input is already inside input; reasoning is already inside output.',
 'input_tokens':'Source input_tokens. Includes cached input and any reported cache-write input.',
 'cached_input_tokens':'Previously processed input reused from cache; a subset of input_tokens.',
 'uncached_input_tokens':'max(input − cached, 0). Input not served from cache; includes cache writes if reported.',
 'cache_write_input_tokens':'Source cache_write_input_tokens / cache_write_tokens only. Missing = N/A, not zero. A reported 0 is displayed as 0.',
 'output_tokens':'Source output_tokens. Already includes reasoning output.',
 'reasoning_output_tokens':'Reasoning tokens reported as part of output usage; not added again to total.',
 'non_reasoning_output_tokens':'max(output − reasoning, 0).',
 'new_work':'Uncached input + output. Newly processed input plus generated output.',
 'cache_hit_ratio':'cached ÷ input × 100. N/A if input is zero or a required field is missing.',
 'output_ratio':'output ÷ official total × 100. N/A if total is zero.',
 'reasoning_ratio':'reasoning ÷ output × 100. N/A if output is zero or reasoning is missing.',
 'comparison_uncached':'Comparison component: input − cache read − cache write. Writes are removed here so the four components do not overlap.',
 'claude_raw':'Comparison only, not the official total. Non-cache/non-write input + cache read + cache write + output. OpenAI and Claude expose caching differently; do not compare their headlines blindly. N/A when a component is unavailable.',
 'known_processed':'Supported subtotal: uncached input + cache read + output. Does not invent a cache-write split or add unknown writes.',
}


def number(value, percent=False):
    return 'N/A' if value is None else f'{value:,.2f}%' if percent else f'{value:,}'


def table(headers):
    t=QTableWidget(0,len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().hide()
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.setStyleSheet('QTableWidget {background:#1C2139;alternate-background-color:#242B45;gridline-color:#3A415F;border:0;} QHeaderView::section {background:#303752;color:#EEF2FF;padding:8px;border:0;} QTableWidget::item {padding:6px;}')
    return t


def populate(t, rows):
    selected=t.currentRow()
    scroll=t.verticalScrollBar().value()
    t.setRowCount(len(rows))
    for row,values in enumerate(rows):
        for col,value in enumerate(values):
            text,tip=value if isinstance(value,tuple) else (str(value),'')
            item=t.item(row,col)
            if item is None:
                item=QTableWidgetItem();t.setItem(row,col,item)
            item.setText(text)
            item.setToolTip(tip)
    if selected>=0 and selected<len(rows):t.selectRow(selected)
    t.verticalScrollBar().setValue(scroll)


class AnalyticsWindow(QDialog):
    def __init__(self,panel):
        super().__init__(panel)
        self.setWindowTitle('petoken · Token Analytics')
        self.setWindowFlag(Qt.Window,True)
        screen=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1020,screen.width()-40),min(750,screen.height()-40))
        layout=QVBoxLayout(self)
        self.heading=QLabel('TOKEN ANALYTICS')
        self.heading.setStyleSheet('font-size:21px;font-weight:600;color:#91E4F2;')
        layout.addWidget(self.heading)
        self.subtitle=QLabel()
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        tabs=QTabWidget()
        tabs.setStyleSheet('QTabWidget::pane {border:1px solid #4C5575;} QTabBar::tab {background:#242B45;padding:11px 14px;} QTabBar::tab:selected {background:#41486C;color:#91E4F2;}')
        layout.addWidget(tabs)
        self.metrics=table(['分组 / Metric','精确值','类型 / 覆盖范围'])
        tabs.addTab(self.metrics,'完整用量')
        self.models=table(['Model','Input','Cached','Uncached','Write','Output','Reasoning','Non-reasoning','Total'])
        tabs.addTab(self.models,'按模型')
        self.sessions=table(['Session','Input','Cached','Uncached','Write','Output','Reasoning','Total'])
        tabs.addTab(self.sessions,'按会话')
        history=QWidget();h=QVBoxLayout(history)
        self.history_note=QLabel('本地索引历史 · 按系统本地时区；包括已归档会话。不是服务器账户的完整 lifetime。')
        self.history_note.setWordWrap(True);h.addWidget(self.history_note)
        self.ranges=table(['范围','Total','Input','Cached','Output','Reasoning'])
        self.ranges.setMaximumHeight(240);h.addWidget(self.ranges)
        self.days=table(['日期 / 本地时区','Total','Input','Cached','Write','Output','Reasoning'])
        h.addWidget(self.days)
        tabs.addTab(history,'日期与历史')
        self.raw=QPlainTextEdit();self.raw.setReadOnly(True)
        self.raw.setStyleSheet('background:#1C2139;color:#DDE6FC;font-family:Consolas;font-size:12px;')
        tabs.addTab(self.raw,'原始字段 / 来源')
        self.note=QLabel('N/A = 缺少可靠数据。鼠标悬停查看公式与精确来源；部分已知小计会单独标注。')
        self.note.setWordWrap(True);layout.addWidget(self.note)
        self.timer_key=None

    def update_data(self,d):
        a=d.get('analytics')
        if not a:return
        self.heading.setText('TOKEN ANALYTICS · '+('整个项目' if d.get('scope')=='project' else '当前任务'))
        self.subtitle.setText(f"{d.get('title','')} · {d.get('project','')} · {a['events']} 个去重用量事件\n模型、会话与完整用量使用当前统计范围；日期与历史使用本地索引全部记录。")
        rows=[]
        fields=[('Official OpenAI','total_tokens','Total Tokens'),('Official OpenAI','input_tokens','Input Tokens'),
            ('Official OpenAI','cached_input_tokens','Cached Input / Cache Read'),('Official OpenAI','uncached_input_tokens','Uncached Input'),
            ('Official OpenAI','output_tokens','Output Tokens'),('Official OpenAI','reasoning_output_tokens','Reasoning Tokens'),
            ('Official OpenAI','non_reasoning_output_tokens','Non-reasoning Output'),('Cache','cache_write_input_tokens','Cache Write'),
            ('Cache','cache_hit_ratio','Cache Hit Ratio'),('Derived','new_work','New / Non-cached Work'),
            ('Derived','output_ratio','Output Ratio'),('Derived','reasoning_ratio','Reasoning Share of Output'),
            ('Comparison','comparison_uncached','Input excluding cache read AND write'),
            ('Comparison','cached_input_tokens','Cache Read component'),('Comparison','cache_write_input_tokens','Cache Write component'),
            ('Comparison','output_tokens','Output component'),('Comparison','claude_raw','Claude-style Raw Processed'),
            ('Comparison','known_processed','Supported processed subtotal')]
        for group,key,caption in fields:
            raw=key in a['tokens'];value=(a['tokens'] if raw else a['derived']).get(key)
            cover=f"raw · {a['coverage'][key]}/{a['events']} events" if raw else 'derived'
            if raw and value is None and a['coverage'][key]:
                cover+=f" · 已知小计 {a['known'][key]:,}"
            if key=='total_tokens':cover='source total；缺失时仅以 input + output 回退'
            rows.append((f'{group} · {caption}',(number(value,key.endswith('ratio')),HELP.get(key,'')),cover))
        populate(self.metrics,rows)
        def values(r,keys):
            return [number(r['tokens'].get(k,r['derived'].get(k))) for k in keys]
        populate(self.models,[[r['name']]+values(r,['input_tokens','cached_input_tokens','uncached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','non_reasoning_output_tokens','total_tokens']) for r in a['models']])
        names=d.get('session_names',{})
        populate(self.sessions,[[(names.get(r['name']) or r['name'],r['name'])]+values(r,['input_tokens','cached_input_tokens','uncached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','total_tokens']) for r in a['sessions']])
        h=d.get('history')
        if h:
            ranges=[('Current session',d['current_session']),('Local recorded lifetime',h),
                    ('Today',h['ranges']['today']),('Last 7 calendar days',h['ranges']['last7']),
                    ('Last 30 calendar days',h['ranges']['last30']),('Undated / unallocated',h['undated'])]
            populate(self.ranges,[[name]+values(r,['total_tokens','input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens']) for name,r in ranges])
            populate(self.days,[[r['name']]+values(r,['total_tokens','input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens']) for r in h['daily']])
            self.history_note.setText('本地索引历史 · 本地时区 / 日历天 · 不包括已删除、云端独有或未同步的记录。'+(' 存在缺失或已排除的继承历史，请视为部分记录。' if h.get('partial') else ''))
        else:
            self.history_note.setText('正在增量读取本地历史…')
        raw=json.dumps(dict(source='Codex JSONL event_msg/token_count/info (current session latest record)',
            total_token_usage=d.get('raw_total'),last_token_usage=d.get('raw_last'),
            model_context_window=d.get('context_window'),timestamp=d.get('sample'),
            model_metadata=d.get('model'),reasoning_effort=d.get('effort'),service_tier=d.get('tier'),
            field_notes='Unknown extra source fields are preserved here but not interpreted or added to totals.',
            notes=d.get('notes',[])),ensure_ascii=False,indent=2)
        if self.raw.toPlainText()!=raw:
            pos=self.raw.verticalScrollBar().value();self.raw.setPlainText(raw);self.raw.verticalScrollBar().setValue(pos)
        self.note.setText('N/A = 缺少可靠数据。'+(' | '.join(d.get('notes',[])) or '缓存输入与 reasoning 均为子项，不会再次计入 Total。'))
