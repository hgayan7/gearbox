import SwiftUI

enum GearboxDesign {
    // Native Apple-like Color Palette
    enum Color {
        static let accent = SwiftUI.Color.accentColor
        static let success = SwiftUI.Color.secondary
        static let warning = SwiftUI.Color.secondary
        static let danger = SwiftUI.Color(nsColor: .systemRed)
        static let background = SwiftUI.Color(nsColor: .windowBackgroundColor)
        static let secondaryBackground = SwiftUI.Color.primary.opacity(0.02)
    }
    
    // Custom View Modifiers
    struct CardModifier: ViewModifier {
        func body(content: Content) -> some View {
            content
                .padding(10)
                .background(VisualEffectView(material: .contentBackground, blendingMode: .withinWindow))
                .cornerRadius(6)
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(SwiftUI.Color.primary.opacity(0.05), lineWidth: 0.5)
                )
        }
    }
    
    struct PremiumPulse: ViewModifier {
        @State private var pulse = false
        let isActive: Bool
        
        func body(content: Content) -> some View {
            content
                .opacity(pulse ? 0.6 : 1.0)
                .onAppear {
                    if isActive {
                        withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                            pulse = true
                        }
                    }
                }
        }
    }
}

extension View {
    func gearboxCard() -> some View {
        self.modifier(GearboxDesign.CardModifier())
    }
    
    func premiumPulse(isActive: Bool) -> some View {
        self.modifier(GearboxDesign.PremiumPulse(isActive: isActive))
    }
}
