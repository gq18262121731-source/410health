import '../../../core/network/api_client.dart';
import '../models/care_directory_model.dart';
import '../models/care_profile_model.dart';

class CareRepository {
  final ApiClient _apiClient;

  CareRepository(this._apiClient);

  Future<CareAccessProfile> getAccessProfile() async {
    final response = await _apiClient.get('care/access-profile/me');
    return CareAccessProfile.fromJson(response.data);
  }

  Future<CareDirectory> getFamilyDirectory(String familyId) async {
    final response = await _apiClient.get('care/directory/family/$familyId');
    return CareDirectory.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> bindSelfDevice({
    required String macAddress,
    String? deviceName,
  }) async {
    final payload = <String, dynamic>{
      'mac_address': macAddress,
    };
    final normalizedName = deviceName?.trim();
    if (normalizedName != null && normalizedName.isNotEmpty) {
      payload['device_name'] = normalizedName;
    }
    await _apiClient.post('devices/bind/self', data: payload);
  }

  Future<void> unbindSelfDevice() async {
    await _apiClient.post('devices/unbind/self');
  }

  Future<void> bindElderCamera({
    required String elderId,
    required String cameraId,
  }) async {
    await _apiClient.put(
      'care/elders/$elderId/camera-binding',
      data: <String, dynamic>{'camera_id': cameraId},
    );
  }

  Future<void> unbindElderCamera({
    required String elderId,
  }) async {
    await _apiClient.delete('care/elders/$elderId/camera-binding');
  }
}
