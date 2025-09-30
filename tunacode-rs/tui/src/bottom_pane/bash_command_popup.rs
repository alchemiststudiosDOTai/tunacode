use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::Stylize;
use ratatui::text::Line;
use ratatui::text::Text;
use ratatui::widgets::Paragraph;
use ratatui::widgets::Widget;
use ratatui::widgets::WidgetRef;
use ratatui::widgets::Wrap;

use crate::render::highlight::highlight_bash_to_lines;
use crate::render::line_utils::prefix_lines;
use tunacode_core::bash::try_parse_bash;

pub(crate) struct BashCommandPopup {
    script: String,
    lines: Vec<Line<'static>>,
    has_error: bool,
}

impl BashCommandPopup {
    pub(crate) fn new() -> Self {
        Self {
            script: String::new(),
            lines: vec![Line::from("Type a bash command after ! to run it".dim())],
            has_error: false,
        }
    }

    pub(crate) fn on_composer_text_change(&mut self, first_line: &str) {
        let script = first_line
            .strip_prefix('!')
            .unwrap_or("")
            .trim_start()
            .to_string();
        self.script = script;
        self.refresh_lines();
    }

    pub(crate) fn calculate_required_height(&self, _width: u16) -> u16 {
        self.lines.len().max(1) as u16
    }

    fn refresh_lines(&mut self) {
        if self.script.is_empty() {
            self.lines = vec![Line::from("Type a bash command after ! to run it".dim())];
            self.has_error = false;
            return;
        }
        let highlighted = highlight_bash_to_lines(&self.script);
        let mut lines = prefix_lines(highlighted, "! ".magenta(), "  ".into());
        self.has_error = try_parse_bash(&self.script).is_none();
        if self.has_error {
            lines.push("Invalid bash syntax — command will not run".red().into());
        } else {
            lines.push("Press Enter to run".dim().into());
        }
        self.lines = lines;
    }
}

impl WidgetRef for BashCommandPopup {
    fn render_ref(&self, area: Rect, buf: &mut Buffer) {
        Paragraph::new(Text::from(self.lines.clone()))
            .wrap(Wrap { trim: false })
            .render(area, buf);
    }
}
