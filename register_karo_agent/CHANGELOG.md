# RegisterKaro Agent Changelog

## [0.2.6] - 2025-03-13

### Added
- Integrated embedded Razorpay checkout for in-app payments
- Added popup payment window instead of redirecting to external links
- Implemented proper Razorpay checkout flow with success/failure handling
- Enhanced payment experience with seamless checkout UI

## [0.2.5] - 2025-03-13

### Fixed
- Fixed payment link format to properly redirect to Razorpay checkout page
- Updated simulated payment URLs to use /l/ path format for proper rendering
- Implemented direct API calls to Razorpay for payment link generation
- Fixed issue where payment links were showing an empty object

## [0.2.4] - 2025-03-13

### Added
- Implemented full Razorpay SDK support in payment flow
- Added proper payment link validation using real API credentials
- Enhanced error handling for payment processing edge cases

## [0.2.3] - 2025-03-13

### Added
- Integrated Razorpay test API credentials for real payment processing
- Enhanced payment flow with real test environment integration
- Added detailed comments for future Razorpay SDK implementation

## [0.2.2] - 2025-03-13

### Fixed
- Fixed document verification rejection messages not appearing in the chat
- Added proper sequencing between sending messages and requesting document upload
- Enhanced error handling in WebSocket communication
- Improved client-side document upload status feedback

## [0.2.1] - 2025-03-13

### Fixed
- Eliminated "Unknown session ID" errors by sending server-generated session ID to client
- Updated document upload and payment verification to use server session ID
- Improved client-side session handling to maintain consistency with server

### Added
- Server now sends its session ID to the client on WebSocket connection
- Client stores both local and server session IDs for reliable operation
- Added comprehensive logging of session ID usage

## [0.2.0] - 2025-03-13

### Fixed
- Improved session ID handling to support prefixed IDs (e.g., "session_xyz123")
- Added robust session ID mapping in document upload and payment verification endpoints
- Fixed document upload failures due to session ID mismatches
- Implemented partial UUID matching as a fallback mechanism
- Ensured consistent use of actual_session_id throughout the application

### Added
- Better logging for session ID mapping operations

## [0.1.0] - Initial Release

- Basic chat functionality with aggressive sales tactics
- Document upload and verification
- Payment link generation via Razorpay API
- Follow-up messages for inactive users
- User information extraction (name, email, phone)