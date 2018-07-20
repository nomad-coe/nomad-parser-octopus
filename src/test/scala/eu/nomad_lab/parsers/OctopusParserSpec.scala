/*
 * Copyright 2015-2018 Ask Hjorth Larsen, Fawzi Mohamed, Ankit Kariryaa
 * 
 *   Licensed under the Apache License, Version 2.0 (the "License");
 *   you may not use this file except in compliance with the License.
 *   You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 *   Unless required by applicable law or agreed to in writing, software
 *   distributed under the License is distributed on an "AS IS" BASIS,
 *   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *   See the License for the specific language governing permissions and
 *   limitations under the License.
 */

package eu.nomad_lab.parsers

import org.specs2.mutable.Specification

object OctopusParserSpec extends Specification {
  "OctopusParserTest" >> {
    "test with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/ink-gs/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/ink-gs/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test H2O with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/H2O/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test H2O with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/H2O/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test O2 with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/O2/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test O2 with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/O2/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test Si with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Si/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test Si with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Si/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test Fe with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Fe/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test Fe with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Fe/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test newFe with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newFe/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test newFe with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newFe/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test newH2O with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newH2O/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test newH2O with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newH2O/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test newO2 with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newO2/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test newO2 with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newO2/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test newSi with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newSi/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test newSi with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/newSi/static/info", "json") must_== ParseResult.ParseSuccess
    }
  }
}
