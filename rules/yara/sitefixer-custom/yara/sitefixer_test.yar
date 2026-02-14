rule sitefixer_test_marker
{
  meta:
    author = "sitefixer"
    description = "Test marker rule"
  strings:
    $m = "SITEFIXER_YARA_TEST_123"
  condition:
    $m
}
