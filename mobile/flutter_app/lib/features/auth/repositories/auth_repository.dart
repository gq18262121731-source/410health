import '../../../core/network/api_client.dart';
import '../../session/models/user_model.dart';

class AuthRepository {
  final ApiClient _apiClient;

  AuthRepository(this._apiClient);

  Future<LoginResponse> login(String username, String password) async {
    final response = await _apiClient.post('/auth/login', data: {
      'username': username,
      'password': password,
    });
    return LoginResponse.fromJson(response.data);
  }

  Future<SessionUser> getMe() async {
    final response = await _apiClient.get('/auth/me');
    return SessionUser.fromJson(response.data);
  }
}
