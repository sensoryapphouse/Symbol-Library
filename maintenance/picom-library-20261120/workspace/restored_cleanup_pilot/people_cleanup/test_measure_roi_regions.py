"""Small metadata fixtures; no image decoding or production artifact changes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('roi_helper',Path(__file__).with_name('measure_roi_regions.py'))
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

class ROIMetadataFixtures(unittest.TestCase):
    def test_rectangle_native_bounds(self):
        self.assertEqual(helper.validate_roi([0,0,1024,512],[1024,512]),(0,0,1024,512))
        for roi in ([0,0,1025,512],[-1,0,1,1],[2,2,2,3],[0,0,1,513],[True,0,1,1],[0,0,1.0,1]):
            with self.subTest(roi=roi),self.assertRaises(ValueError):helper.validate_roi(roi,[1024,512])
    def test_max_dimension_normalization(self):
        self.assertEqual(helper.normalize(1024,[1024,512]),256)
        self.assertEqual(helper.normalize(1024,[512,1024]),256)
        self.assertEqual(helper.normalize(256,[512,512]),256)
        self.assertLess(helper.normalize(1023,[1024,512]),256)
    def test_namespace_and_nested_path_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);allowed=root/'production'/'batches';allowed.mkdir(parents=True)
            good=allowed/'batch031';good.mkdir();nested=good/'nested';nested.mkdir();other=root/'outside';other.mkdir()
            with patch.object(helper,'ALLOWED',(allowed.resolve(),)):
                self.assertEqual(helper.validate_batch(good),good.resolve())
                for path in (allowed,nested,other):
                    with self.subTest(path=path),self.assertRaises(ValueError):helper.validate_batch(path)
                alias=allowed/'alias';alias.symlink_to(other,target_is_directory=True)
                with self.assertRaises(ValueError):helper.validate_batch(alias)

if __name__=='__main__':unittest.main()
