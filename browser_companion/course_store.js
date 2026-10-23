globalThis.LearningCourses=(()=>{
  function parse(reply){
    let text=reply.trim().replace(/^```(?:json)?\s*/i,"").replace(/\s*```$/,"");
    const value=JSON.parse(text);
    function str(object,key,max=4000){if(typeof object[key]!=="string" || !object[key].trim() || object[key].length>max)throw new Error("课程字段无效："+key);return object[key].trim();}
    const course={title:str(value,"title",200),goal:str(value,"goal"),prerequisite_check:str(value,"prerequisite_check"),exercise:str(value,"exercise"),acceptance:str(value,"acceptance"),limitations:str(value,"limitations")};
    if(!Array.isArray(value.sections) || value.sections.length<2 || value.sections.length>4)throw new Error("课程应包含2–4个知识点");
    course.sections=value.sections.map(section=>({title:str(section,"title",200),explanation:str(section,"explanation",5000),example:str(section,"example"),question:str(section,"question")}));
    if(!Array.isArray(value.resources) || value.resources.length>12)throw new Error("课程资源格式无效");
    course.resources=value.resources.map(resource=>{const url=new URL(str(resource,"url",3000));if(!["https:","http:"].includes(url.protocol) || url.username || url.password)throw new Error("资源链接不安全");return {title:str(resource,"title",300),url:url.href,note:str(resource,"note",1000)};});
    return course;
  }
  const key=direction=>"learningCourses:"+direction;
  async function list(direction){const stored=await chrome.storage.local.get(key(direction));return stored[key(direction)] || [];}
  async function save(direction,course){const courses=await list(direction);await chrome.storage.local.set({[key(direction)]:[...courses.filter(item=>item.id!==course.id),course]});}
  return {parse,list,save};
})();
