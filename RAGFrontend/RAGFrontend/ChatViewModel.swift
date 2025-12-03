//
//  ChatViewModel.swift
//  RAGFrontend
//
//  Created by Prathmesh Parteki on 01/12/25.
//

import SwiftUI
import Combine
import Foundation

struct Message: Identifiable {
    let id = UUID()
    var text: String
    let isUser: Bool
    let timestamp: Date = Date()
    var isStreaming: Bool = false
}

// MARK: - Request Models
struct ChatRequest: Codable {
    let message: String
    let session_id: String
    let k: Int
    let verbose: Bool
}

// MARK: - Response Models
struct PDFUploadResponse: Codable {
    let message: String
    let filename: String
    let sessionId: String
    let cloudinaryUrl: String
    let cloudinaryPublicId: String
    let chunksCreated: Int
    let textLength: Int
    
    enum CodingKeys: String, CodingKey {
        case message
        case filename
        case sessionId = "session_id"
        case cloudinaryUrl = "cloudinary_url"
        case cloudinaryPublicId = "cloudinary_public_id"
        case chunksCreated = "chunks_created"
        case textLength = "text_length"
    }
}

struct ChatResponse: Codable {
    let message: String
    let answer: String
    let sessionId: String
    let contextualizedQuestion: String?
    let sources: [Source]?
    let numSources: Int?
    
    enum CodingKeys: String, CodingKey {
        case message
        case answer
        case sessionId = "session_id"
        case contextualizedQuestion = "contextualized_question"
        case sources
        case numSources = "num_sources"
    }
    
    struct Source: Codable {
        let content: String
        let metadata: [String: String]?
    }
}

class ChatViewModel: ObservableObject {
    
    @Published var messages: [Message] = []
    @Published var isLoading: Bool = false
    @Published var isThinking: Bool = false
    @Published var errorMessage: String?
    @Published var uploadedFileName: String?
    
    private let baseURL = "http://localhost:8000"
    private let sessionId = "user_123"
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Send Message
    func sendMessage(_ text: String) {
        guard !text.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        
        let userMessage = Message(text: text, isUser: true)
        messages.append(userMessage)
        
        isLoading = true
        isThinking = true
        errorMessage = nil
        
        getChatResponse(for: text)
    }
    
    private func getChatResponse(for userInput: String) {
        guard let url = URL(string: "\(baseURL)/chat") else {
            handleError("Invalid URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30
        
        let requestBody = ChatRequest(
            message: userInput,
            session_id: sessionId,
            k: 3,
            verbose: false
        )
        
        do {
            let encoder = JSONEncoder()
            request.httpBody = try encoder.encode(requestBody)
            
            if let jsonString = String(data: request.httpBody!, encoding: .utf8) {
                print("📤 Request: \(jsonString)")
            }
        } catch {
            handleError("Failed to encode request: \(error.localizedDescription)")
            return
        }
        
        URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { output -> Data in
                guard let httpResponse = output.response as? HTTPURLResponse else {
                    throw URLError(.badServerResponse)
                }
                
                print("📥 Response Status: \(httpResponse.statusCode)")
                
                guard (200...299).contains(httpResponse.statusCode) else {
                    let bodyString = String(data: output.data, encoding: .utf8) ?? "<no body>"
                    print("❌ Error Body: \(bodyString)")
                    throw URLError(.init(rawValue: httpResponse.statusCode))
                }
                
                if let jsonString = String(data: output.data, encoding: .utf8) {
                    print("📥 Response: \(jsonString)")
                }
                
                return output.data
            }
            .decode(type: ChatResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                switch completion {
                case .failure(let error):
                    print("❌ Error: \(error)")
                    self?.isThinking = false
                    self?.isLoading = false
                    self?.handleError("Network error: \(error.localizedDescription)")
                case .finished:
                    print("✅ Request completed successfully")
                    break
                }
            } receiveValue: { [weak self] response in
                guard let self = self else { return }
                
                self.isThinking = false
                
                let streamingMessage = Message(text: "", isUser: false, isStreaming: true)
                self.messages.append(streamingMessage)
                
                self.animateText(response.answer, for: self.messages.count - 1)
            }
            .store(in: &cancellables)
    }
    
    private func animateText(_ fullText: String, for index: Int) {
        let characters = Array(fullText)
        var currentIndex = 0
        
        Timer.scheduledTimer(withTimeInterval: 0.02, repeats: true) { [weak self] timer in
            guard let self = self else {
                timer.invalidate()
                return
            }
            
            if currentIndex < characters.count {
                let substring = String(characters[0...currentIndex])
                self.messages[index].text = substring
                currentIndex += 1
            } else {
                self.messages[index].isStreaming = false
                self.isLoading = false
                timer.invalidate()
            }
        }
    }
    
    // MARK: - Upload PDF
    func uploadPDF(url: URL, completion: @escaping (Result<PDFUploadResponse, Error>) -> Void) {
        guard let uploadURL = URL(string: "\(baseURL)/upload") else {
            completion(.failure(NSError(domain: "Invalid URL", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid upload URL"])))
            return
        }
        
        var request = URLRequest(url: uploadURL)
        request.httpMethod = "POST"
        request.timeoutInterval = 60 // Longer timeout for file upload
        
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        do {
            // Read PDF data
            let pdfData = try Data(contentsOf: url)
            let fileName = url.lastPathComponent
            
            // Build multipart form data
            var body = Data()
            
            // Add file field
            body.append("--\(boundary)\r\n")
            body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n")
            body.append("Content-Type: application/pdf\r\n\r\n")
            body.append(pdfData)
            body.append("\r\n")
            
            // Add session_id field
            body.append("--\(boundary)\r\n")
            body.append("Content-Disposition: form-data; name=\"session_id\"\r\n\r\n")
            body.append("\(sessionId)\r\n")
            
            // End boundary
            body.append("--\(boundary)--\r\n")
            
            request.httpBody = body
            
            print("📤 Uploading PDF: \(fileName) (\(pdfData.count) bytes)")
            
            URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
                DispatchQueue.main.async {
                    // Handle network error
                    if let error = error {
                        print("❌ Upload network error: \(error.localizedDescription)")
                        completion(.failure(error))
                        return
                    }
                    
                    // Validate HTTP response
                    guard let httpResponse = response as? HTTPURLResponse else {
                        let error = NSError(domain: "Invalid response", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid HTTP response"])
                        completion(.failure(error))
                        return
                    }
                    
                    print("📥 Upload Status: \(httpResponse.statusCode)")
                    
                    // Check status code
                    guard (200...299).contains(httpResponse.statusCode) else {
                        let errorMsg = String(data: data ?? Data(), encoding: .utf8) ?? "Unknown error"
                        print("❌ Upload failed: \(errorMsg)")
                        let error = NSError(
                            domain: "Upload Failed",
                            code: httpResponse.statusCode,
                            userInfo: [NSLocalizedDescriptionKey: errorMsg]
                        )
                        completion(.failure(error))
                        return
                    }
                    
                    // Parse response
                    guard let data = data else {
                        let error = NSError(domain: "No data received", code: -1, userInfo: [NSLocalizedDescriptionKey: "No data in response"])
                        completion(.failure(error))
                        return
                    }
                    
                    // Debug: Print raw response
                    if let jsonString = String(data: data, encoding: .utf8) {
                        print("📥 Upload Response: \(jsonString)")
                    }
                    
                    do {
                        let decoder = JSONDecoder()
                        let uploadResponse = try decoder.decode(PDFUploadResponse.self, from: data)
                        print("✅ Upload successful: \(uploadResponse.filename)")
                        print("   - Saved to: \(uploadResponse.cloudinaryUrl)")
                        print("   - Chunks created: \(uploadResponse.chunksCreated)")
                        print("   - Text length: \(uploadResponse.textLength)")
                        
                        self?.uploadedFileName = uploadResponse.filename
                        completion(.success(uploadResponse))
                        
                    } catch {
                        print("❌ Failed to decode response: \(error)")
                        if let jsonString = String(data: data, encoding: .utf8) {
                            print("   Raw response: \(jsonString)")
                        }
                        completion(.failure(error))
                    }
                }
            }.resume()
            
        } catch {
            print("❌ Failed to read PDF: \(error.localizedDescription)")
            completion(.failure(error))
        }
    }
    
    func clearUploadedPDF() {
        uploadedFileName = nil
    }
    
    private func handleError(_ message: String) {
        isLoading = false
        isThinking = false
        errorMessage = message
        
        let errorMsg = Message(text: "Error: \(message)", isUser: false)
        messages.append(errorMsg)
    }
    
    func clearChat() {
        messages.removeAll()
        errorMessage = nil
    }
}

// MARK: - Data Extension Helper
extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}
