//
//  MessageListView.swift
//  RAGFrontend
//
//  Created by Prathmesh Parteki on 01/12/25.
//

import SwiftUI

struct MessageListView: View {
    @ObservedObject var viewModel: ChatViewModel
    
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.messages) { message in
                        MessageRow(message: message)
                            .id(message.id)
                    }
                    
                    // Show thinking bubble while waiting for response
                    if viewModel.isThinking {
                        ThinkingBubble()
                            .id("thinking")
                            .transition(.opacity.combined(with: .scale))
                    }
                }
                .padding(.vertical, 10)
            }
            .onChange(of: viewModel.messages.count) { _ in
                scrollToBottom(proxy: proxy)
            }
            .onChange(of: viewModel.isThinking) { _ in
                scrollToBottom(proxy: proxy)
            }
            // Also scroll when message text changes (for streaming effect)
            .onChange(of: viewModel.messages.last?.text) { _ in
                if viewModel.messages.last?.isStreaming == true {
                    scrollToBottom(proxy: proxy, animated: false)
                }
            }
        }
    }
    
    private func scrollToBottom(proxy: ScrollViewProxy, animated: Bool = true) {
        if animated {
            withAnimation {
                if viewModel.isThinking {
                    proxy.scrollTo("thinking", anchor: .bottom)
                } else if let lastMessage = viewModel.messages.last {
                    proxy.scrollTo(lastMessage.id, anchor: .bottom)
                }
            }
        } else {
            if let lastMessage = viewModel.messages.last {
                proxy.scrollTo(lastMessage.id, anchor: .bottom)
            }
        }
    }
}

struct MessageRow: View {
    let message: Message
    
    var body: some View {
        HStack(spacing: 0) {
            if message.isUser {
                Spacer()
            }
            
            Text(message.text)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 20)
                        .fill(message.isUser ? Color.purple.opacity(0.5) : Color.gray.opacity(0.15))
                )
                .foregroundColor(message.isUser ? .white : .primary)
            
            if !message.isUser {
                Spacer()
            }
        }
        .padding(.horizontal, 15)
    }
}

#Preview {
    MessageListView(viewModel: ChatViewModel())
}
