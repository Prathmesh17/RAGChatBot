//
//  ThinkingBubble.swift
//  RAGFrontend
//
//  Created by Prathmesh Parteki on 01/12/25.
//

import SwiftUI

struct ThinkingBubble: View {
    @Environment(\.colorScheme) var colorScheme
    
    var body: some View {
        HStack(spacing: 0) {
            ShimmerView(
                shape: RoundedRectangle(cornerRadius: 0),
                color: shimmerColor
            )
            .mask(
                Text("Thinking...")
                    .font(.title3)
                    .fontWeight(.semibold)
            )
            .frame(width: 110, height: 22)
            
            Spacer()
        }
        .padding(.horizontal, 15)
    }
    
    // Adaptive color for shimmer based on color scheme
    private var shimmerColor: Color {
        colorScheme == .dark
            ? Color.white.opacity(0.4)
            : Color.black.opacity(0.3)
    }
}

#Preview("Light Mode") {
    VStack(spacing: 20) {
        ThinkingBubble()
        
        Divider()
        
        // Show with message context
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Spacer()
                Text("What is AI?")
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(20)
            }
            
            ThinkingBubble()
        }
        .padding()
    }
    .preferredColorScheme(.light)
}

#Preview("Dark Mode") {
    VStack(spacing: 20) {
        ThinkingBubble()
        
        Divider()
        
        // Show with message context
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Spacer()
                Text("What is AI?")
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(20)
            }
            
            ThinkingBubble()
        }
        .padding()
    }
    .preferredColorScheme(.dark)
    .background(Color.black)
}

// MARK: - Shimmer View
struct ShimmerView<S: Shape>: View {
    var shape: S
    var color: Color
    
    init(shape: S, color: Color = .gray.opacity(0.3)) {
        self.shape = shape
        self.color = color
    }
    
    @State private var isAnimating: Bool = false
    @Environment(\.colorScheme) var colorScheme
    
    var body: some View {
        shape
            .fill(color)
            .overlay {
                GeometryReader { geometry in
                    let size = geometry.size
                    let shimmerWidth = size.width
                    let blurRadius = max(shimmerWidth / 2, 30)
                    let blurDiameter = blurRadius * 2
                    let minX = -(shimmerWidth + blurDiameter)
                    let maxX = size.width + shimmerWidth + blurDiameter
                    
                    Rectangle()
                        .fill(shimmerGradient)
                        .frame(width: shimmerWidth, height: size.height * 2)
                        .frame(height: size.height)
                        .blur(radius: blurRadius)
                        .rotationEffect(.init(degrees: rotation))
                        .blendMode(.overlay)
                        .offset(x: isAnimating ? maxX : minX)
                }
            }
            .clipShape(shape)
            .compositingGroup()
            .onAppear {
                guard !isAnimating else { return }
                withAnimation(animation) {
                    isAnimating = true
                }
            }
            .onDisappear {
                isAnimating = false
            }
            .transaction {
                if $0.animation != animation {
                    $0.animation = .none
                }
            }
    }
    
    // Adaptive shimmer gradient based on color scheme
    private var shimmerGradient: LinearGradient {
        LinearGradient(
            colors: colorScheme == .dark
                ? [.white.opacity(0.3), .white.opacity(0.7), .white.opacity(0.3)]
                : [.gray.opacity(0.3), .white, .gray.opacity(0.3)],
            startPoint: .leading,
            endPoint: .trailing
        )
    }
    
    var rotation: Double {
        return 6
    }
    
    var animation: Animation {
        .linear(duration: 1.5).repeatForever(autoreverses: false)
    }
}

#Preview("Shimmer Circle - Light") {
    @Previewable
    @State var isTapped: Bool = false
    ShimmerView(shape: .circle)
        .frame(width: 100, height: 100)
        .onTapGesture {
            withAnimation(.smooth) {
                isTapped.toggle()
            }
        }
        .padding(.bottom, isTapped ? 15 : 0)
        .preferredColorScheme(.light)
}

#Preview("Shimmer Circle - Dark") {
    @Previewable
    @State var isTapped: Bool = false
    ShimmerView(shape: .circle)
        .frame(width: 100, height: 100)
        .onTapGesture {
            withAnimation(.smooth) {
                isTapped.toggle()
            }
        }
        .padding(.bottom, isTapped ? 15 : 0)
        .preferredColorScheme(.dark)
        .background(Color.black)
}
