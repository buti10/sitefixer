rule Sitefixer_Test_String {
  strings:
    $a = "SITEFIXER_YARA_TEST_123"
  condition:
    $a
}
