import SwiftUI
import CAPTCoreDesktop

// MARK: - Inversion Labs native visual language
//
// This layer deliberately stays on top of standard macOS SwiftUI controls and
// materials. It gives CAPT a coherent visual grammar without replacing native
// sidebars, toolbars, sheets, focus, accessibility, or appearance adaptation.

enum InversionTone {
    case neutral
    case amber
    case cyan
    case success
    case warning
    case danger
    case violet

    var color: Color {
        switch self {
        case .neutral: return .secondary
        case .amber: return Color(red: 0.70, green: 0.54, blue: 0.32)
        case .cyan: return Color(red: 0.71, green: 0.71, blue: 0.68)
        case .success: return Color(red: 0.39, green: 0.64, blue: 0.48)
        case .warning: return Color(red: 0.77, green: 0.55, blue: 0.29)
        case .danger: return Color(red: 0.79, green: 0.39, blue: 0.35)
        case .violet: return Color(red: 0.74, green: 0.67, blue: 0.55)
        }
    }
}

enum InversionVisualLanguage {
    static let pagePadding: CGFloat = 24
    static let sectionSpacing: CGFloat = 18
    static let panelPadding: CGFloat = 16
    static let radius: CGFloat = 12
    static let compactRadius: CGFloat = 8

    static func tone(forState raw: String) -> InversionTone {
        switch CAPTRuntimeStateSemantics.tone(for: raw) {
        case .neutral: return .neutral
        case .success: return .success
        case .danger: return .danger
        case .warning: return .amber
        case .active: return .cyan
        case .violet: return .violet
        }
    }
}

struct InversionPanel<Content: View>: View {
    let tone: InversionTone
    let padding: CGFloat
    @ViewBuilder var content: Content

    init(
        tone: InversionTone = .neutral,
        padding: CGFloat = InversionVisualLanguage.panelPadding,
        @ViewBuilder content: () -> Content
    ) {
        self.tone = tone
        self.padding = padding
        self.content = content()
    }

    var body: some View {
        content
            .padding(padding)
            .background {
                RoundedRectangle(cornerRadius: InversionVisualLanguage.radius, style: .continuous)
                    .fill(Color(nsColor: .controlBackgroundColor))
            }
            .overlay {
                RoundedRectangle(cornerRadius: InversionVisualLanguage.radius, style: .continuous)
                    .strokeBorder(tone.color.opacity(tone == .neutral ? 0.10 : 0.22), lineWidth: 1)
            }
    }
}

struct InversionSectionHeader: View {
    let eyebrow: String?
    let title: String
    let detail: String?
    let symbol: String?
    let tone: InversionTone

    init(
        _ title: String,
        eyebrow: String? = nil,
        detail: String? = nil,
        symbol: String? = nil,
        tone: InversionTone = .neutral
    ) {
        self.title = title
        self.eyebrow = eyebrow
        self.detail = detail
        self.symbol = symbol
        self.tone = tone
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            if let symbol {
                ZStack {
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(tone.color.opacity(0.12))
                    Image(systemName: symbol)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(tone.color)
                }
                .frame(width: 34, height: 34)
            }
            VStack(alignment: .leading, spacing: 4) {
                if let eyebrow {
                    Text(eyebrow.uppercased())
                        .font(.caption2.weight(.semibold))
                        .tracking(1.25)
                        .foregroundStyle(tone.color)
                }
                Text(title)
                    .font(.title3.weight(.semibold))
                if let detail {
                    Text(detail)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
    }
}

struct InversionStatusBadge: View {
    let text: String
    let tone: InversionTone
    let monospaced: Bool

    init(_ text: String, tone: InversionTone? = nil, monospaced: Bool = false) {
        self.text = text
        self.tone = tone ?? InversionVisualLanguage.tone(forState: text)
        self.monospaced = monospaced
    }

    var body: some View {
        Text(text.replacingOccurrences(of: "_", with: " ").uppercased())
            .font(monospaced ? .caption2.monospaced().weight(.semibold) : .caption2.weight(.semibold))
            .tracking(0.45)
            .foregroundStyle(tone.color)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(tone.color.opacity(0.10), in: Capsule())
            .overlay {
                Capsule().strokeBorder(tone.color.opacity(0.22), lineWidth: 1)
            }
    }
}

struct InversionMetric: View {
    let label: String
    let value: String
    let symbol: String?
    let tone: InversionTone

    init(_ label: String, value: String, symbol: String? = nil, tone: InversionTone = .neutral) {
        self.label = label
        self.value = value
        self.symbol = symbol
        self.tone = tone
    }

    var body: some View {
        HStack(spacing: 8) {
            if let symbol {
                Image(systemName: symbol)
                    .foregroundStyle(tone.color)
            }
            VStack(alignment: .leading, spacing: 1) {
                Text(value)
                    .font(.callout.monospacedDigit().weight(.semibold))
                Text(label.uppercased())
                    .font(.caption2)
                    .tracking(0.7)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
    }
}

struct InversionKeyValueRow: View {
    let label: String
    let value: String
    let tone: InversionTone
    let monospaced: Bool

    init(_ label: String, value: String, tone: InversionTone = .neutral, monospaced: Bool = false) {
        self.label = label
        self.value = value
        self.tone = tone
        self.monospaced = monospaced
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(label.uppercased())
                .font(.caption2.weight(.medium))
                .tracking(0.8)
                .foregroundStyle(.secondary)
                .frame(width: 112, alignment: .leading)
            Text(value)
                .font(monospaced ? .caption.monospaced() : .callout)
                .foregroundStyle(tone == .neutral ? Color.primary : tone.color)
                .textSelection(.enabled)
            Spacer(minLength: 0)
        }
    }
}

struct InversionDivider: View {
    var body: some View {
        Rectangle()
            .fill(Color.primary.opacity(0.08))
            .frame(height: 1)
    }
}

struct InversionBrandMark: View {
    let compact: Bool

    init(compact: Bool = false) { self.compact = compact }

    var body: some View {
        HStack(spacing: compact ? 7 : 10) {
            ZStack {
                RoundedRectangle(cornerRadius: compact ? 5 : 7)
                    .strokeBorder(Color.primary.opacity(0.42), lineWidth: 1)
                Text("C")
                    .font(.system(size: compact ? 10 : 13, weight: .bold, design: .monospaced))
                    .foregroundStyle(.primary)
            }
            .frame(width: compact ? 20 : 26, height: compact ? 20 : 26)

            if !compact {
                VStack(alignment: .leading, spacing: 0) {
                    Text("CAPT")
                        .font(.headline.weight(.semibold))
                    Text("INVERSION LABS")
                        .font(.system(size: 8, weight: .semibold))
                        .tracking(1.35)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("CAPT by Inversion Labs")
    }
}
