/*
   Copyright 2016-2017 The NOMAD Developers Group

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
 */
package eu.nomad_lab.parsers

import eu.{ nomad_lab => lab }
import eu.nomad_lab.DefaultPythonInterpreter
import org.{ json4s => jn }
import scala.collection.breakOut
import eu.nomad_lab.parsers.AncillaryFilesPrefilter.{ ParentSubtree => ParentSubtree }
import eu.nomad_lab.parsers.AncillaryFilesPrefilter.{ WholeUpload => WholeUpload }

object OctopusParser extends SimpleExternalParserGenerator(
  name = "OctopusParser",
  parserInfo = jn.JObject(
    ("name" -> jn.JString("OctopusParser")) ::
      ("parserId" -> jn.JString("OctopusParser" + lab.OctopusVersionInfo.version)) ::
      ("versionInfo" -> jn.JObject(
        ("nomadCoreVersion" -> jn.JObject(lab.NomadCoreVersionInfo.toMap.map {
          case (k, v) => k -> jn.JString(v.toString)
        }(breakOut): List[(String, jn.JString)])) ::
          (lab.OctopusVersionInfo.toMap.map {
            case (key, value) =>
              (key -> jn.JString(value.toString))
          }(breakOut): List[(String, jn.JString)])
      )) :: Nil
  ),
  mainFileTypes = Seq("text/.*"),
  //TODO: Update the replacement string (mainFileRe)
  mainFileRe = """\*{32} Grid \*{32}
Simulation Box:
""".r,
  cmd = Seq(DefaultPythonInterpreter.pythonExe(), "${envDir}/parsers/octopus/parser/parser-octopus/parser_octopus.py",
    "${mainFilePath}"),
  ancillaryFilesPrefilter = ParentSubtree,
  resList = Seq(
    "parser-octopus/parser_octopus.py",
    "parser-octopus/aseoct.py",
    "parser-octopus/octopus_logfile_parser.py",
    "parser-octopus/generate-octopus-json.py",
    "parser-octopus/util.py",
    "parser-octopus/octopus_info_parser.py",
    "parser-octopus/setup_paths.py",
    "nomad_meta_info/public.nomadmetainfo.json",
    "nomad_meta_info/common.nomadmetainfo.json",
    "nomad_meta_info/meta_types.nomadmetainfo.json",
    "nomad_meta_info/octopus.autogenerated.nomadmetainfo.json",
    "nomad_meta_info/octopus.nomadmetainfo.json"
  ) ++ DefaultPythonInterpreter.commonFiles(),
  dirMap = Map(
    "parser-octopus" -> "parsers/octopus/parser/parser-octopus",
    "nomad_meta_info" -> "nomad-meta-info/meta_info/nomad_meta_info"
  ) ++ DefaultPythonInterpreter.commonDirMapping()
)
