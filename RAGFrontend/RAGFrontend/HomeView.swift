//
//  HomeView.swift
//  RAGFrontend
//
//  Created by Prathmesh Parteki on 01/12/25.
//

import SwiftUI
import UniformTypeIdentifiers

struct HomeView: View {
    @StateObject private var viewModel = ChatViewModel()
    @State private var text: String = ""
    @FocusState private var isFocused: Bool
    @State private var showPDFPicker = false
    @State private var uploadedPDFName: String?
    @State private var isUploading: Bool = false
    @State private var uploadProgress: String = ""
    @State private var showToast: Bool = false
    @State private var toastMessage: String = ""
    @State private var toastType: ToastType = .success
    
    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                // Modern Header
                modernHeader
                
                Divider()
                
                // Messages
                MessageListView(viewModel: viewModel)
                
                // Modern Composer
                modernComposer
            }
            
            // Toast Notification
            if showToast {
                VStack {
                    Spacer()
                    ToastView(message: toastMessage, type: toastType)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                        .padding(.bottom, 100)
                }
                .animation(.spring(response: 0.6, dampingFraction: 0.8), value: showToast)
            }
        }
        .sheet(isPresented: $showPDFPicker) {
            PDFPickerView { url in
                uploadPDF(url: url)
            }
        }
    }
    
    // MARK: - Modern Header
    private var modernHeader: some View {
        VStack(spacing: 0) {
            HStack(spacing: 16) {
                // App Icon
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [.blue, .purple],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: "brain.head.profile")
                        .font(.title3)
                        .foregroundColor(.white)
                        .fontWeight(.semibold)
                }
                
                // Title & Status
                VStack(alignment: .leading, spacing: 4) {
                    Text("RAG Assistant")
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundStyle(
                            LinearGradient(
                                colors: [.blue, .purple],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                    
                    if let pdfName = uploadedPDFName {
                        HStack(spacing: 6) {
                            Image(systemName: "doc.text.fill")
                                .font(.caption2)
                                .foregroundColor(.green)
                            
                            Text(pdfName)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                            
                            Button {
                                withAnimation(.spring(response: 0.3)) {
                                    uploadedPDFName = nil
                                    viewModel.clearUploadedPDF()
                                }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.caption)
                                    .foregroundColor(.red.opacity(0.7))
                            }
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(8)
                    } else if isUploading {
                        HStack(spacing: 6) {
                            ProgressView()
                                .scaleEffect(0.7)
                            Text(uploadProgress)
                                .font(.caption)
                                .foregroundColor(.blue)
                        }
                    } else {
                        Text("Ask me anything...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                // Actions
                HStack(spacing: 12) {
                    // Upload indicator
                    if isUploading {
                        ProgressView()
                            .scaleEffect(0.8)
                    }
                    
                    // Clear chat
                    Button {
                        withAnimation {
                            viewModel.clearChat()
                            uploadedPDFName = nil
                        }
                    } label: {
                        ZStack {
                            Circle()
                                .fill(Color.red.opacity(0.1))
                                .frame(width: 36, height: 36)
                            
                            Image(systemName: "trash.fill")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                    .disabled(isUploading)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .background(
                LinearGradient(
                    colors: [
                        Color(UIColor.systemBackground),
                        Color(UIColor.systemBackground).opacity(0.95)
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
            )
        }
    }
    
    // MARK: - Modern Composer
    private var modernComposer: some View {
        VStack(spacing: 0) {
            Divider()
            
            HStack(spacing: 12) {
                // Action Buttons
                HStack(spacing: 8) {
                    // Upload PDF
                    Button {
                        showPDFPicker = true
                    } label: {
                        ZStack {
                            Circle()
                                .fill(uploadedPDFName != nil ? Color.green.opacity(0.15) : Color.gray.opacity(0.1))
                                .frame(width: 36, height: 36)
                            
                            Image(systemName: uploadedPDFName != nil ? "checkmark.circle.fill" : "paperclip")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(uploadedPDFName != nil ? .green : .primary)
                        }
                    }
                    .disabled(isUploading)
                    
                    // Search (optional)
                    Button {
                        // Search action
                    } label: {
                        ZStack {
                            Circle()
                                .fill(Color.gray.opacity(0.1))
                                .frame(width: 36, height: 36)
                            
                            Image(systemName: "magnifyingglass")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(.primary)
                        }
                    }
                }
                
                // Text Input
                HStack(spacing: 8) {
                    TextField("Ask anything...", text: $text, axis: .vertical)
                        .focused($isFocused)
                        .lineLimit(1...4)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(20)
                    
                    // Send Button
                    Button {
                        if !text.trimmingCharacters(in: .whitespaces).isEmpty {
                            viewModel.sendMessage(text)
                            text = ""
                            isFocused = false
                        }
                    } label: {
                        ZStack {
                            Circle()
                                .fill(
                                    (viewModel.isLoading || isUploading || text.isEmpty)
                                    ? LinearGradient(
                                        colors: [.purple, .blue],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    )
                                    : LinearGradient(
                                        colors: [.blue, .purple],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    )
                                )
                                .frame(width: 40, height: 40)
                            
                            Image(systemName: "arrow.up")
                                .font(.system(size: 16, weight: .bold))
                                .foregroundColor(
                                    (viewModel.isLoading || isUploading || text.isEmpty)
                                    ? .gray
                                    : .white
                                )
                        }
                    }
                    .disabled(viewModel.isLoading || isUploading || text.isEmpty)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color(UIColor.systemBackground))
        }
    }
    
    // MARK: - Upload PDF
    private func uploadPDF(url: URL) {
        isUploading = true
        uploadProgress = "Processing..."
        
        viewModel.uploadPDF(url: url) { result in
            isUploading = false
            uploadProgress = ""
            
            switch result {
            case .success(let response):
                uploadedPDFName = response.filename
                
                // Show success toast
                showToastMessage(
                    "✅ \(response.filename) uploaded successfully!",
                    type: .success
                )
                
            case .failure(let error):
                // Show error toast
                showToastMessage(
                    "❌ Upload failed: \(error.localizedDescription)",
                    type: .error
                )
            }
        }
    }
    
    private func showToastMessage(_ message: String, type: ToastType) {
        toastMessage = message
        toastType = type
        
        withAnimation(.spring(response: 0.6, dampingFraction: 0.8)) {
            showToast = true
        }
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.8)) {
                showToast = false
            }
        }
    }
}

// MARK: - Toast View
enum ToastType {
    case success, error, info
    
    var color: Color {
        switch self {
        case .success: return .green
        case .error: return .red
        case .info: return .blue
        }
    }
    
    var icon: String {
        switch self {
        case .success: return "checkmark.circle.fill"
        case .error: return "xmark.circle.fill"
        case .info: return "info.circle.fill"
        }
    }
}

struct ToastView: View {
    let message: String
    let type: ToastType
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: type.icon)
                .font(.title3)
                .foregroundColor(.white)
            
            Text(message)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.white)
                .lineLimit(2)
            
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(type.color)
                .shadow(color: type.color.opacity(0.4), radius: 12, x: 0, y: 4)
        )
        .padding(.horizontal, 20)
    }
}

#Preview {
    HomeView()
}
